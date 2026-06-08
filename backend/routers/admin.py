"""
管理员控制台 API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from database import get_session
from models import Package, PackageStatus, Employee
from datetime import datetime, timedelta

router = APIRouter(prefix="/admin/api")


@router.get("/packages")
def list_packages(
    status: str = "",
    days: int = 30,
    session: Session = Depends(get_session),
):
    """所有包裹列表，可按状态和天数过滤"""
    since = datetime.now() - timedelta(days=days)
    q = select(Package).where(Package.arrived_at >= since).order_by(Package.arrived_at.desc())
    if status:
        q = q.where(Package.status == status)
    pkgs = session.exec(q).all()
    return [
        {
            "id":         p.id,
            "code":       p.code,
            "courier":    p.courier,
            "phone_tail": p.phone_tail,
            "status":     p.status,
            "arrived_at": p.arrived_at.strftime("%Y/%m/%d %H:%M"),
            "picked_at":  p.picked_at.strftime("%Y/%m/%d %H:%M") if p.picked_at else None,
        }
        for p in pkgs
    ]


@router.post("/packages/{pkg_id}/pickup")
def force_pickup(pkg_id: int, session: Session = Depends(get_session)):
    """管理员手动标记已取件"""
    pkg = session.get(Package, pkg_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="包裹不存在")
    pkg.status    = PackageStatus.picked_up
    pkg.picked_at = datetime.now()
    session.add(pkg)
    session.commit()
    return {"ok": True, "code": pkg.code}


@router.get("/stats")
def stats(days: int = 30, session: Session = Depends(get_session)):
    """报表数据"""
    since = datetime.now() - timedelta(days=days)
    all_pkgs = session.exec(
        select(Package).where(Package.arrived_at >= since)
    ).all()

    total     = len(all_pkgs)
    picked_up = sum(1 for p in all_pkgs if p.status == PackageStatus.picked_up)
    pending   = sum(1 for p in all_pkgs if p.status == PackageStatus.pending)
    unclaimed = sum(1 for p in all_pkgs if p.status == PackageStatus.unclaimed)

    # 快递公司分布
    courier_map: dict[str, int] = {}
    for p in all_pkgs:
        courier_map[p.courier] = courier_map.get(p.courier, 0) + 1

    # 近 days 天每日入库量
    daily: dict[str, int] = {}
    for p in all_pkgs:
        day = p.arrived_at.strftime("%m/%d")
        daily[day] = daily.get(day, 0) + 1

    # 平均取件时长（小时）
    durations = [
        (p.picked_at - p.arrived_at).total_seconds() / 3600
        for p in all_pkgs
        if p.picked_at and p.status == PackageStatus.picked_up
    ]
    avg_hours = round(sum(durations) / len(durations), 1) if durations else 0

    return {
        "total":      total,
        "picked_up":  picked_up,
        "pending":    pending,
        "unclaimed":  unclaimed,
        "avg_hours":  avg_hours,
        "by_courier": courier_map,
        "daily":      daily,
    }


@router.get("/employee-stats")
def employee_stats(days: int = 30, session: Session = Depends(get_session)):
    """员工收件排行（按收件量降序，Top 20）"""
    since = datetime.now() - timedelta(days=days)
    pkgs = session.exec(
        select(Package).where(Package.arrived_at >= since, Package.employee_id != None)
    ).all()
    emp_map = {e.employee_id: e.name for e in session.exec(select(Employee)).all()}
    counter: dict[str, int] = {}
    for p in pkgs:
        name = emp_map.get(p.employee_id, p.phone_tail or "未知")
        counter[name] = counter.get(name, 0) + 1
    ranked = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    return [{"name": n, "count": c} for n, c in ranked[:20]]


@router.get("/trend")
def trend(days: int = 90, session: Session = Depends(get_session)):
    """历史周趋势（按周聚合）"""
    since = datetime.now() - timedelta(days=days)
    pkgs = session.exec(
        select(Package).where(Package.arrived_at >= since)
    ).all()
    weekly: dict[str, int] = {}
    for p in pkgs:
        week_num = (p.arrived_at.day - 1) // 7 + 1
        week = p.arrived_at.strftime("%m月") + f"W{week_num}"
        weekly[week] = weekly.get(week, 0) + 1
    return weekly
