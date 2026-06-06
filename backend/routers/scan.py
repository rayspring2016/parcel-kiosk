from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel
from datetime import datetime
from database import get_session
from models import Package, PackageStatus
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


@router.post("/scan")
async def scan(req: ScanRequest, session: Session = Depends(get_session)):
    result             = parse_barcode(req.barcode)
    shelf, layer, seq  = assign_location(session, MAX_SHELVES, MAX_LAYERS)
    code               = f"{shelf}-{layer}-{seq:04d}"
    dt                 = DingTalkClient(DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID)
    now_str            = datetime.now().strftime("%Y/%m/%d %H:%M")

    employee_id = None
    if result.phone:
        employee_id = await dt.get_user_id_by_phone(result.phone)

    if employee_id:
        pkg = Package(
            shelf=shelf, layer=layer, seq=seq, code=code,
            courier=result.courier, employee_id=employee_id
        )
        session.add(pkg)
        session.commit()
        session.refresh(pkg)
        pickup_url = f"{SERVER_BASE_URL}/pickup/confirm/{pkg.id}"
        await dt.send_pickup_notification(employee_id, code, result.courier, pickup_url)
        try:
            get_printer_service().print_label(
                shelf=shelf, layer=layer, seq=seq,
                courier=result.courier, arrived_at=now_str
            )
        except Exception as e:
            import logging; logging.getLogger(__name__).warning("打印失败（可忽略）: %s", e)
        return {"matched": True, "code": code, "courier": result.courier, "pkg_id": pkg.id}
    else:
        pkg = Package(
            shelf=shelf, layer=layer, seq=seq, code=code,
            courier=result.courier,
            status=PackageStatus.unclaimed,
            phone_tail=result.phone[-4:] if result.phone else None,
        )
        session.add(pkg)
        session.commit()
        session.refresh(pkg)
        try:
            get_printer_service().print_unclaimed_label(
                shelf=shelf, layer=layer, seq=seq,
                courier=result.courier, arrived_at=now_str
            )
        except Exception as e:
            import logging; logging.getLogger(__name__).warning("打印失败（可忽略）: %s", e)
        return {"matched": False, "code": code, "courier": result.courier, "pkg_id": pkg.id}
