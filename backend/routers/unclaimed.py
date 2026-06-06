from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from database import get_session
from models import Package, PackageStatus

router = APIRouter()


@router.get("/unclaimed")
def list_unclaimed(session: Session = Depends(get_session)):
    pkgs = session.exec(
        select(Package).where(Package.status == PackageStatus.unclaimed)
    ).all()
    return [
        {
            "pkg_id":    p.id,
            "code":      p.code,
            "shelf":     p.shelf,
            "layer":     p.layer,
            "courier":   p.courier,
            "arrived_at": p.arrived_at,
            "phone_tail": p.phone_tail,
        }
        for p in pkgs
    ]


class ClaimRequest(BaseModel):
    employee_id: str


@router.post("/unclaimed/{pkg_id}/claim")
def claim_package(pkg_id: int, req: ClaimRequest, session: Session = Depends(get_session)):
    """员工认领待认领包裹：绑定 employee_id，状态改为 pending"""
    pkg = session.get(Package, pkg_id)
    if not pkg or pkg.status != PackageStatus.unclaimed:
        raise HTTPException(status_code=404, detail="包裹不存在或已被认领")
    pkg.employee_id = req.employee_id
    pkg.status      = PackageStatus.pending
    session.add(pkg)
    session.commit()
    return {"pkg_id": pkg.id, "code": pkg.code, "employee_id": pkg.employee_id, "status": pkg.status}
