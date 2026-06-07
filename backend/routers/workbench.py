from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/workbench", response_class=HTMLResponse)
def workbench_page():
    return HTMLResponse(_HTML)


_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
  <title>快递取件</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system,"PingFang SC",sans-serif; background:#f5f7fa; color:#1a1a2e; min-height:100vh; }
    .header { background:#fff; padding:16px 20px 12px; border-bottom:1px solid #eee; position:sticky; top:0; z-index:10; }
    .header h1 { font-size:18px; font-weight:700; }
    .header p  { font-size:13px; color:#888; margin-top:2px; }
    .content { padding:16px; }
    /* 登录框 */
    .login-card { background:#fff; border-radius:16px; padding:28px 20px; text-align:center; box-shadow:0 2px 8px rgba(0,0,0,.08); }
    .login-card h2 { font-size:17px; margin-bottom:6px; }
    .login-card p  { font-size:13px; color:#888; margin-bottom:20px; }
    .input-row { display:flex; gap:10px; }
    .input-row input { flex:1; padding:13px 14px; border:1.5px solid #e0e0e0; border-radius:10px; font-size:17px; letter-spacing:0.15em; text-align:center; }
    .input-row input:focus { outline:none; border-color:#1E88E5; }
    .input-row button { padding:13px 18px; background:#1E88E5; color:#fff; border:none; border-radius:10px; font-size:15px; font-weight:600; cursor:pointer; white-space:nowrap; }
    .input-row button:active { opacity:.85; }
    /* 包裹卡片 */
    .card { background:#fff; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 1px 4px rgba(0,0,0,.06); }
    .badge { display:inline-block; font-size:11px; padding:2px 8px; border-radius:99px; margin-bottom:8px; font-weight:600; }
    .badge-pending  { background:#fff3cd; color:#856404; }
    .badge-pickedup { background:#d4edda; color:#155724; }
    .code { font-size:26px; font-weight:800; letter-spacing:.05em; }
    .row { display:flex; justify-content:space-between; font-size:14px; padding:8px 0; border-bottom:1px solid #f0f0f0; }
    .row:last-of-type { border-bottom:none; }
    .row span { color:#888; }
    .btn { display:block; width:100%; margin-top:14px; padding:13px; background:#1E88E5; color:#fff; border:none; border-radius:10px; font-size:16px; font-weight:600; cursor:pointer; }
    .btn:active { opacity:.85; transform:scale(.98); }
    .btn-done { background:#e8f5e9; color:#2e7d32; }
    .btn-sm { width:auto; display:inline-block; padding:6px 14px; font-size:13px; background:#f0f0f0; color:#555; margin-top:16px; border-radius:8px; border:none; cursor:pointer; }
    .empty { text-align:center; padding:60px 20px; color:#aaa; }
    .empty .icon { font-size:48px; display:block; margin-bottom:12px; }
    .err { color:#c00; font-size:14px; margin-top:10px; }
  </style>
</head>
<body>
<div class="header">
  <h1>我的包裹</h1>
  <p id="greeting">…</p>
</div>
<div class="content" id="content"></div>

<script>
const API = location.origin
const KEY  = 'pkiosk_eid'

function init() {
  const eid = localStorage.getItem(KEY)
  if (eid) {
    loadPackages(eid)
  } else {
    showLogin()
  }
}

function showLogin() {
  document.getElementById('greeting').textContent = '请先验证身份'
  document.getElementById('content').innerHTML = `
    <div class="login-card">
      <h2>验证手机尾号</h2>
      <p>输入你手机号后 4 位</p>
      <div class="input-row">
        <input id="tail" type="tel" maxlength="4" placeholder="0000" inputmode="numeric">
        <button onclick="doLogin()">确认</button>
      </div>
      <p class="err" id="err"></p>
    </div>`
  setTimeout(() => document.getElementById('tail').focus(), 100)
}

function doLogin() {
  const tail = document.getElementById('tail').value.trim()
  if (tail.length !== 4) { document.getElementById('err').textContent = '请输入 4 位数字'; return }
  fetch(API + '/employees/by-tail/' + tail)
    .then(r => r.json())
    .then(data => {
      if (data.error) { document.getElementById('err').textContent = data.error; return }
      localStorage.setItem(KEY, data.employee_id)
      loadPackages(data.employee_id)
    })
    .catch(() => { document.getElementById('err').textContent = '网络错误，请重试' })
}

function loadPackages(eid) {
  document.getElementById('greeting').textContent = '加载中…'
  fetch(API + '/my-packages?employee_id=' + eid)
    .then(r => r.json())
    .then(pkgs => renderPackages(eid, pkgs))
    .catch(() => { document.getElementById('greeting').textContent = '加载失败'; })
}

function renderPackages(eid, pkgs) {
  document.getElementById('greeting').textContent = '以下是你的包裹'
  const pending  = pkgs.filter(p => p.status === 'pending')
  const pickedup = pkgs.filter(p => p.status === 'picked_up').slice(0, 3)
  let html = ''
  if (pkgs.length === 0) {
    html = '<div class="empty"><span class="icon">📭</span>暂无包裹记录</div>'
  } else {
    if (pending.length)  html += '<p style="font-size:13px;color:#888;margin-bottom:8px">待取件</p>'
    pending.forEach(p  => { html += cardHtml(p, true)  })
    if (pickedup.length) html += '<p style="font-size:13px;color:#888;margin:16px 0 8px">最近已取（3条）</p>'
    pickedup.forEach(p => { html += cardHtml(p, false) })
  }
  html += '<button class="btn-sm" onclick="logout()">切换账号</button>'
  document.getElementById('content').innerHTML = html
}

function cardHtml(p, showBtn) {
  const arrived = new Date(p.arrived_at).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'})
  const badge = showBtn ? '<span class="badge badge-pending">待取件</span>' : '<span class="badge badge-pickedup">已取件</span>'
  const btn   = showBtn
    ? `<button class="btn" onclick="confirmPickup(${p.pkg_id},this)">✅ 确认已取件</button>`
    : `<button class="btn btn-done" disabled>✓ 已取件</button>`
  return `<div class="card">${badge}<div class="code">${p.code}</div>
    <div class="row"><span>位置</span><b>货架 ${p.shelf} — 第 ${p.layer} 层</b></div>
    <div class="row"><span>快递公司</span><b>${p.courier}</b></div>
    <div class="row"><span>到件时间</span><b>${arrived}</b></div>${btn}</div>`
}

function confirmPickup(pkgId, btn) {
  btn.disabled = true; btn.textContent = '确认中…'
  fetch(API + '/pickup/' + pkgId, {method:'POST'})
    .then(r => r.json())
    .then(() => {
      btn.textContent = '✓ 已确认'; btn.className = 'btn btn-done'
      const eid = localStorage.getItem(KEY)
      setTimeout(() => loadPackages(eid), 800)
    })
    .catch(() => { btn.disabled=false; btn.textContent='✅ 确认已取件'; alert('操作失败，请重试') })
}

function logout() { localStorage.removeItem(KEY); showLogin() }

init()
</script>
</body>
</html>"""
