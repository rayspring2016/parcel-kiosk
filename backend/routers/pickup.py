from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from datetime import datetime
from database import get_session
from models import Package, PackageStatus

router = APIRouter()


@router.post("/pickup/{slot}")
def confirm_pickup(slot: int, session: Session = Depends(get_session)):
    """小程序调用：员工确认取走某格子的包裹"""
    pkg = session.exec(
        select(Package)
        .where(Package.slot == slot)
        .where(Package.status == PackageStatus.pending)
    ).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="该格子无待取包裹")
    pkg.status   = PackageStatus.picked_up
    pkg.picked_at = datetime.now()
    session.add(pkg)
    session.commit()
    return {"status": "picked_up", "slot": slot, "picked_at": pkg.picked_at}


@router.get("/my-packages")
def my_packages(employee_id: str, session: Session = Depends(get_session)):
    pkgs = session.exec(
        select(Package).where(Package.employee_id == employee_id)
    ).all()
    return [
        {
            "slot": p.slot,
            "code": p.code,
            "courier": p.courier,
            "arrived_at": p.arrived_at,
            "status": p.status,
        }
        for p in pkgs
    ]


@router.get("/pickup/confirm/{pkg_id}")
def confirm_pickup_page(pkg_id: int, session: Session = Depends(get_session)):
    """OA 消息 message_url 点击后触发（GET，钉钉不支持 POST 跳转）。
    用 pkg_id 而非 slot，避免槽位复用后新旧通知混淆。"""
    pkg = session.get(Package, pkg_id)
    if not pkg or pkg.status == PackageStatus.picked_up:
        return HTMLResponse("<h2>✓ 包裹已确认取件</h2>", status_code=200)
    pkg.status   = PackageStatus.picked_up
    pkg.picked_at = datetime.now()
    session.add(pkg)
    session.commit()
    return HTMLResponse(
        f"<h2>✓ 取件确认成功</h2>"
        f"<p>格子编号：<b>{pkg.slot:02d}</b></p>"
        f"<p>感谢确认！该格子已释放。</p>",
        status_code=200
    )
