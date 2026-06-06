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
            "slot": p.slot,
            "code": p.code,
            "courier": p.courier,
            "arrived_at": p.arrived_at,
            "phone_tail": p.phone_tail,
        }
        for p in pkgs
    ]


class ClaimRequest(BaseModel):
    employee_id: str


@router.post("/unclaimed/{slot}/claim")
def claim_package(slot: int, req: ClaimRequest, session: Session = Depends(get_session)):
    """员工认领待认领包裹：找到该格子当前的 unclaimed 包裹，绑定 employee_id → pending"""
    pkg = session.exec(
        select(Package)
        .where(Package.slot == slot)
        .where(Package.status == PackageStatus.unclaimed)
    ).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="该格子无待认领包裹")
    pkg.employee_id = req.employee_id
    pkg.status      = PackageStatus.pending
    session.add(pkg)
    session.commit()
    return {"slot": pkg.slot, "employee_id": pkg.employee_id, "status": pkg.status}
