from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from database import get_session
from models import Package, PackageStatus, Employee
from services.barcode import parse_barcode
from services.code_gen import assign_location
from services.dingtalk import DingTalkClient
from services.printer import get_printer_service
from config import (DINGTALK_APP_KEY, DINGTALK_APP_SECRET,
                    DINGTALK_AGENT_ID, SERVER_BASE_URL,
                    MAX_SHELVES, MAX_LAYERS)

router = APIRouter()


class ScanRequest(BaseModel):
    barcode: str


class AssignRequest(BaseModel):
    phone_tail: str


@router.post("/scan")
async def scan(req: ScanRequest, session: Session = Depends(get_session)):
    """扫码 → 立即分配编号、入库、打印标签"""
    result = parse_barcode(req.barcode)

    shelf, layer, seq = assign_location(session, MAX_SHELVES, MAX_LAYERS)
    code    = f"{shelf}-{layer}-{seq:04d}"
    now_str = datetime.now().strftime("%Y/%m/%d %H:%M")

    pkg = Package(
        shelf=shelf, layer=layer, seq=seq, code=code,
        courier=result.courier, status=PackageStatus.unclaimed,
    )
    session.add(pkg); session.commit(); session.refresh(pkg)

    try:
        get_printer_service().print_label(
            shelf=shelf, layer=layer, seq=seq,
            courier=result.courier, arrived_at=now_str)
    except Exception as e:
        import logging; logging.getLogger(__name__).warning("打印失败: %s", e)

    return {
        "code":    code,
        "pkg_id":  pkg.id,
        "courier": result.courier,
        "status":  "need_phone",
    }


@router.post("/scan/{pkg_id}/assign")
async def assign_employee(
    pkg_id: int, req: AssignRequest, session: Session = Depends(get_session)
):
    """输入手机尾号 → 匹配员工并推送（重复时带位置推送给所有候选人）"""
    pkg = session.get(Package, pkg_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="包裹不存在")

    candidates = session.exec(
        select(Employee).where(Employee.phone_tail == req.phone_tail)
    ).all()

    dt = DingTalkClient(DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID)

    if len(candidates) == 1:
        # 唯一匹配：直接推送取件通知
        emp = candidates[0]
        pkg.employee_id = emp.employee_id
        pkg.status      = PackageStatus.pending
        pkg.phone_tail  = req.phone_tail
        session.add(pkg); session.commit()

        pickup_url = f"{SERVER_BASE_URL}/pickup/confirm/{pkg.id}"
        try:
            await dt.send_pickup_notification(
                emp.employee_id, pkg.code, pkg.courier, pickup_url)
        except Exception as e:
            import logging; logging.getLogger(__name__).warning("推送失败: %s", e)

        return {"status": "matched", "employee_name": emp.name}

    elif len(candidates) > 1:
        # 重复匹配：带货架位置推送给所有候选人，让员工自己认领
        pkg.phone_tail = req.phone_tail
        session.add(pkg); session.commit()

        review_urls = {
            e.employee_id: f"{SERVER_BASE_URL}/unclaimed/{pkg.id}/review?employee_id={e.employee_id}"
            for e in candidates
        }
        try:
            await dt.send_ambiguous_notification(
                employee_review_urls=review_urls,
                courier=pkg.courier,
                tracking_tail=req.phone_tail,
                code=pkg.code,
            )
        except Exception as e:
            import logging; logging.getLogger(__name__).warning("推送失败: %s", e)

        return {"status": "ambiguous_notified", "count": len(candidates)}

    else:
        # 无匹配：保持待认领
        pkg.phone_tail = req.phone_tail
        session.add(pkg); session.commit()
        return {"status": "unmatched"}
