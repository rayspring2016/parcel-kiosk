from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from datetime import datetime
from database import get_session
from models import Package, PackageStatus

router = APIRouter()


@router.post("/pickup/{pkg_id}")
def confirm_pickup(pkg_id: int, session: Session = Depends(get_session)):
    """小程序调用：员工确认取走包裹"""
    pkg = session.get(Package, pkg_id)
    if not pkg or pkg.status != PackageStatus.pending:
        raise HTTPException(status_code=404, detail="包裹不存在或已取件")
    pkg.status    = PackageStatus.picked_up
    pkg.picked_at = datetime.now()
    session.add(pkg)
    session.commit()
    return {"status": "picked_up", "code": pkg.code, "picked_at": pkg.picked_at}


@router.get("/my-packages")
def my_packages(employee_id: str, session: Session = Depends(get_session)):
    pkgs = session.exec(
        select(Package).where(Package.employee_id == employee_id)
    ).all()
    return [
        {
            "pkg_id":     p.id,
            "code":       p.code,
            "shelf":      p.shelf,
            "layer":      p.layer,
            "courier":    p.courier,
            "arrived_at": p.arrived_at,
            "status":     p.status,
        }
        for p in pkgs
    ]


@router.get("/pickup/confirm/{pkg_id}", response_class=HTMLResponse)
def confirm_pickup_page(pkg_id: int, session: Session = Depends(get_session)):
    """OA 通知点击后：展示包裹详情，等员工手动点击确认按钮"""
    pkg = session.get(Package, pkg_id)

    if not pkg:
        return HTMLResponse(_page("包裹不存在", "<p class='muted'>该包裹记录不存在，请联系前台。</p>", show_btn=False))

    if pkg.status == PackageStatus.picked_up:
        t = pkg.picked_at.strftime('%m/%d %H:%M')
        return HTMLResponse(_page(
            "已确认取件",
            f"<p class='muted'>取件编号 <b>{pkg.code}</b> 已于 {t} 确认取走。</p>",
            show_btn=False
        ))

    arrived = pkg.arrived_at.strftime('%Y/%m/%d %H:%M')
    body = (
        f"<div class='info-row'><span>取件编号</span><b>{pkg.code}</b></div>"
        f"<div class='info-row'><span>位置</span><b>货架 {pkg.shelf} — 第 {pkg.layer} 层</b></div>"
        f"<div class='info-row'><span>快递公司</span><b>{pkg.courier}</b></div>"
        f"<div class='info-row'><span>到件时间</span><b>{arrived}</b></div>"
    )
    return HTMLResponse(_page("你有包裹到了", body, show_btn=True, pkg_id=pkg_id))


@router.post("/pickup/confirm/{pkg_id}", response_class=HTMLResponse)
def do_confirm_pickup(pkg_id: int, session: Session = Depends(get_session)):
    """用户在详情页点击「确认已取件」按钮后触发"""
    pkg = session.get(Package, pkg_id)
    if not pkg or pkg.status == PackageStatus.picked_up:
        return HTMLResponse(_page("已确认取件", "<p class='muted'>该包裹已经确认取走了。</p>", show_btn=False))
    pkg.status    = PackageStatus.picked_up
    pkg.picked_at = datetime.now()
    session.add(pkg)
    session.commit()
    return HTMLResponse(_page(
        "✅ 取件确认成功",
        f"<p>编号 <b>{pkg.code}</b> 已取走，感谢确认！</p>",
        show_btn=False
    ))


def _page(title: str, body_html: str, show_btn: bool, pkg_id: int = 0) -> str:
    btn = (
        f"<form method='post' action='/pickup/confirm/{pkg_id}'>"
        "<button type='submit' class='btn'>✅ 确认已取件</button>"
        "</form>"
    ) if show_btn else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>快递取件</title>
  <style>
    body {{ font-family: -apple-system, sans-serif; max-width: 480px; margin: 40px auto; padding: 0 20px; color: #1a1a2e; }}
    h2   {{ font-size: 1.4rem; margin-bottom: 1.5rem; }}
    .info-row {{ display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #eee; font-size: 1rem; }}
    .info-row span {{ color: #888; }}
    .info-row b    {{ color: #1a1a2e; }}
    .muted {{ color: #888; }}
    .btn {{ margin-top: 2rem; width: 100%; padding: 14px; background: #1E88E5;
            color: #fff; border: none; border-radius: 10px; font-size: 1.1rem;
            cursor: pointer; font-weight: 600; }}
    .btn:active {{ opacity: 0.85; }}
  </style>
</head>
<body>
  <h2>{title}</h2>
  {body_html}
  {btn}
</body>
</html>"""
