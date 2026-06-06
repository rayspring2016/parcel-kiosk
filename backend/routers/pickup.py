from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from datetime import datetime
from database import get_session
from models import Package, PackageStatus

router = APIRouter()


@router.post("/pickup/{code}")
def confirm_pickup(code: str, session: Session = Depends(get_session)):
    pkg = session.exec(select(Package).where(Package.code == code)).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    if pkg.status == PackageStatus.picked_up:
        raise HTTPException(status_code=400, detail="Already picked up")
    pkg.status = PackageStatus.picked_up
    pkg.picked_at = datetime.now()
    session.add(pkg)
    session.commit()
    return {"status": "picked_up", "code": code, "picked_at": pkg.picked_at}


@router.get("/my-packages")
def my_packages(employee_id: str, session: Session = Depends(get_session)):
    pkgs = session.exec(select(Package).where(Package.employee_id == employee_id)).all()
    return [{"code": p.code, "courier": p.courier, "arrived_at": p.arrived_at, "status": p.status} for p in pkgs]


@router.get("/pickup/{code}/confirm")
def confirm_pickup_page(code: str, session: Session = Depends(get_session)):
    """OA 消息 message_url 点击后触发此 GET 端点（钉钉不支持 POST 跳转）"""
    pkg = session.exec(select(Package).where(Package.code == code)).first()
    if not pkg or pkg.status == PackageStatus.picked_up:
        return HTMLResponse("<h2>✓ 包裹已确认取件</h2>", status_code=200)
    pkg.status = PackageStatus.picked_up
    pkg.picked_at = datetime.now()
    session.add(pkg)
    session.commit()
    return HTMLResponse(
        f"<h2>✓ 取件确认成功</h2><p>包裹编号：{code}</p><p>感谢确认！</p>",
        status_code=200
    )
