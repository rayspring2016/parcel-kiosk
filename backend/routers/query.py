"""
员工自助查询 API
GET /api/query?q=<手机尾号4位 或 货架编号如1-2-0017>
"""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, or_
from database import get_session
from models import Package, PackageStatus

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
