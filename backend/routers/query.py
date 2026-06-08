"""
员工自助查询 API
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import Session, select, or_
from database import get_session
from models import Package, PackageStatus
from datetime import datetime

router = APIRouter(prefix="/api")


@router.get("/query")
def query_packages(
    q: str = Query(..., description="手机尾号(4位) 或 货架编号(如1-2-0017)"),
    session: Session = Depends(get_session),
):
    q = q.strip()

    # 按手机尾号查（4位数字）
    if q.isdigit() and len(q) == 4:
        pkgs = session.exec(
            select(Package).where(
                Package.phone_tail == q,
                or_(
                    Package.status == PackageStatus.pending,
                    Package.status == PackageStatus.unclaimed,
                ),
            )
        ).all()
    else:
        # 按货架编号查（精确匹配，如 1-2-0017）
        pkgs = session.exec(
            select(Package).where(Package.code == q.upper())
        ).all()

    return [
        {
            "id":         p.id,
            "code":       p.code,
            "courier":    p.courier,
            "status":     p.status,
            "arrived_at": p.arrived_at.strftime("%Y/%m/%d %H:%M"),
        }
        for p in pkgs
    ]


@router.post("/api/claim/{pkg_id}")
def claim_package(
    pkg_id: int,
    phone_tail: str = Query(..., description="手机尾号4位"),
    session: Session = Depends(get_session),
):
    """查询页面用：输入手机尾号直接认领包裹（无需钉钉同步）"""
    if len(phone_tail) != 4 or not phone_tail.isdigit():
        raise HTTPException(status_code=400, detail="手机尾号必须是4位数字")
    pkg = session.get(Package, pkg_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="包裹不存在")
    if pkg.status in (PackageStatus.picked_up, PackageStatus.expired):
        raise HTTPException(status_code=400, detail="包裹已取件或已过期")
    pkg.phone_tail = phone_tail
    if not pkg.employee_id:
        pkg.employee_id = f"tail_{phone_tail}"
    pkg.status = PackageStatus.pending
    session.add(pkg)
    session.commit()
    return {"ok": True, "code": pkg.code, "status": pkg.status}
