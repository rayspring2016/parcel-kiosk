from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from pydantic import BaseModel
from database import get_session
from models import Package, PackageStatus
from services.dingtalk import DingTalkClient
from config import DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID, SERVER_BASE_URL
from datetime import datetime

router = APIRouter()


@router.get("/unclaimed")
def list_unclaimed(session: Session = Depends(get_session)):
    pkgs = session.exec(
        select(Package).where(Package.status == PackageStatus.unclaimed)
    ).all()
    return [
        {
            "pkg_id":     p.id,
            "code":       p.code,
            "shelf":      p.shelf,
            "layer":      p.layer,
            "courier":    p.courier,
            "arrived_at": p.arrived_at,
            "phone_tail": p.phone_tail,
        }
        for p in pkgs
    ]


# ── 认领确认页（OA 推送中的个人专属链接）──

@router.get("/unclaimed/{pkg_id}/review", response_class=HTMLResponse)
def review_page(pkg_id: int, employee_id: str, session: Session = Depends(get_session)):
    """员工点击推送后打开：展示快递信息，选择「是我的」或「不是我的」"""
    pkg = session.get(Package, pkg_id)
    if not pkg:
        return HTMLResponse(_review_page("找不到该包裹", "<p class='muted'>记录不存在，请联系前台。</p>", pkg_id, employee_id, show_btns=False))

    if pkg.status != PackageStatus.unclaimed:
        return HTMLResponse(_review_page("已被认领", "<p class='muted'>该包裹已被认领或已取走。</p>", pkg_id, employee_id, show_btns=False))

    arrived = pkg.arrived_at.strftime("%Y/%m/%d %H:%M")
    tail    = f"···{pkg.phone_tail}" if pkg.phone_tail else "—"
    body = (
        f"<div class='info-row'><span>快递公司</span><b>{pkg.courier}</b></div>"
        f"<div class='info-row'><span>单号尾号</span><b>{tail}</b></div>"
        f"<div class='info-row'><span>货架位置</span><b>货架 {pkg.shelf} — 第 {pkg.layer} 层</b></div>"
        f"<div class='info-row'><span>到件时间</span><b>{arrived}</b></div>"
    )
    return HTMLResponse(_review_page("有快递可能是你的", body, pkg_id, employee_id, show_btns=True))


@router.post("/unclaimed/{pkg_id}/review", response_class=HTMLResponse)
async def do_claim_review(pkg_id: int, employee_id: str, session: Session = Depends(get_session)):
    """员工点击「是我的，认领」→ 绑定员工 → 发取件通知"""
    pkg = session.get(Package, pkg_id)
    if not pkg or pkg.status != PackageStatus.unclaimed:
        return HTMLResponse(_review_page("已被认领", "<p class='muted'>该包裹已被认领。</p>", pkg_id, employee_id, show_btns=False))

    pkg.employee_id = employee_id
    pkg.status      = PackageStatus.pending
    session.add(pkg)
    session.commit()

    # 发取件通知，和正常匹配流程一致
    pickup_url = f"{SERVER_BASE_URL}/pickup/confirm/{pkg.id}"
    try:
        dt = DingTalkClient(DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID)
        await dt.send_pickup_notification(employee_id, pkg.code, pkg.courier, pickup_url)
    except Exception:
        pass

    return HTMLResponse(_review_page(
        "✅ 认领成功",
        f"<p>包裹 <b>{pkg.code}</b> 已归入你名下，稍后会收到取件通知。</p>",
        pkg_id, employee_id, show_btns=False
    ))


# ── 小程序 API 认领（兼容旧接口）──

class ClaimRequest(BaseModel):
    employee_id: str


@router.post("/unclaimed/{pkg_id}/claim")
async def claim_package(pkg_id: int, req: ClaimRequest, session: Session = Depends(get_session)):
    """小程序调用：员工认领待认领包裹，认领后发取件通知"""
    pkg = session.get(Package, pkg_id)
    if not pkg or pkg.status != PackageStatus.unclaimed:
        raise HTTPException(status_code=404, detail="包裹不存在或已被认领")

    pkg.employee_id = req.employee_id
    pkg.status      = PackageStatus.pending
    session.add(pkg)
    session.commit()

    pickup_url = f"{SERVER_BASE_URL}/pickup/confirm/{pkg.id}"
    try:
        dt = DingTalkClient(DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID)
        await dt.send_pickup_notification(req.employee_id, pkg.code, pkg.courier, pickup_url)
    except Exception:
        pass

    return {"pkg_id": pkg.id, "code": pkg.code,
            "employee_id": pkg.employee_id, "status": pkg.status}


def _review_page(title, body_html, pkg_id, employee_id, show_btns):
    claim_form = f"""
    <form method="post" action="/unclaimed/{pkg_id}/review?employee_id={employee_id}">
      <button type="submit" class="btn btn-yes">✅ 是我的，认领</button>
    </form>
    <a href="/" class="btn btn-no">❌ 不是我的</a>
    """ if show_btns else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>快递认领</title>
  <style>
    body {{ font-family: -apple-system, sans-serif; max-width: 480px; margin: 40px auto; padding: 0 20px; color: #1a1a2e; }}
    h2   {{ font-size: 1.4rem; margin-bottom: 1.5rem; }}
    .info-row {{ display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #eee; font-size: 1rem; }}
    .info-row span {{ color: #888; }}
    .muted {{ color: #888; }}
    .btn {{ display: block; margin-top: 1rem; width: 100%; padding: 14px; border-radius: 10px;
            font-size: 1.1rem; font-weight: 600; cursor: pointer; text-align: center;
            text-decoration: none; box-sizing: border-box; }}
    .btn-yes {{ background: #1E88E5; color: #fff; border: none; }}
    .btn-no  {{ background: #f5f5f5; color: #888; border: none; margin-top: .75rem; }}
    .btn:active {{ opacity: 0.85; }}
  </style>
</head>
<body>
  <h2>{title}</h2>
  {body_html}
  {claim_form}
</body>
</html>"""
