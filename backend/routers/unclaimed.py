from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from database import get_session
from models import Package, PackageStatus

router = APIRouter()


@router.get("/unclaimed")
def list_unclaimed(session: Session = Depends(get_session)):
    pkgs = session.exec(select(Package).where(Package.status == PackageStatus.unclaimed)).all()
    return [{"code": p.code, "courier": p.courier, "arrived_at": p.arrived_at, "phone_tail": p.phone_tail} for p in pkgs]


class ClaimRequest(BaseModel):
    employee_id: str


@router.post("/unclaimed/{code}/claim")
def claim_package(code: str, req: ClaimRequest, session: Session = Depends(get_session)):
    pkg = session.exec(select(Package).where(Package.code == code)).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    if pkg.status != PackageStatus.unclaimed:
        raise HTTPException(status_code=400, detail="Package is not unclaimed")
    pkg.employee_id = req.employee_id
    pkg.status = PackageStatus.pending
    session.add(pkg)
    session.commit()
    return {"code": pkg.code, "employee_id": pkg.employee_id, "status": pkg.status}
