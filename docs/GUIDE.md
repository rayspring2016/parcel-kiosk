# 快递自助取件系统 · 使用手册

> 最后更新：2026-06-07

---

## 目录

1. [系统概述](#系统概述)
2. [组件说明](#组件说明)
3. [快速启动（本机）](#快速启动本机)
4. [NAS 部署](#nas-部署)
5. [API 接口速查](#api-接口速查)
6. [环境变量说明](#环境变量说明)
7. [日常运维](#日常运维)
8. [常见问题](#常见问题)

---

## 系统概述

公司快递间自助管理系统，解决员工找快递慢的问题。

**核心流程：**
```
快递员扫码 → 系统分配货架位置 → 打印标签 → 匹配员工 → 钉钉推送通知 → 员工取件确认
```

**三种场景：**
- 🟢 **正常**：手机尾号唯一匹配 → 直接推送取件通知
- 🟡 **重复**：尾号对应多名员工 → 推送给所有候选人认领
- 🔴 **无法识别**：找不到员工 → 放入待认领，工作台可查

---

## 组件说明

| 组件 | 路径 | 说明 |
|------|------|------|
| 后端 API | `backend/` | FastAPI + SQLite，核心逻辑 |
| Kiosk 前端 | `kiosk/` | Vue 3，快递员扫码界面 |
| 工作台页面 | `/workbench` | 员工查包裹、确认取件的 H5 页面 |
| 钉钉集成 | `backend/services/dingtalk.py` | 推送通知、员工同步 |
| 打印服务 | `backend/services/printer.py` | 通过 CUPS 打印标签 |

---

## 快速启动（本机）

### 后端

```bash
cd backend
.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### Kiosk 前端（开发模式）

```bash
cd kiosk
npm run dev -- --host 0.0.0.0
# 访问 http://本机IP:5173
```

### 测试全链路

```bash
# 1. 模拟扫码
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"barcode":"SF1234567890123"}'

# 2. 输入手机尾号（替换 PKG_ID 和 TAIL）
curl -X POST http://localhost:8000/scan/PKG_ID/assign \
  -H "Content-Type: application/json" \
  -d '{"phone_tail":"TAIL"}'

# 3. 同步员工
curl -X POST http://localhost:8000/employees/sync
```

---

## NAS 部署

### 前置条件

- 群晖 DS218+，DSM 7.x
- 已安装 Container Manager（Docker）
- 已开启 SSH（控制面板 → 终端机和 SNMP）

### 步骤

**1. Mac 上打包**

```bash
cd parcel-kiosk
cd kiosk && npm run build && cd ..
cp -r kiosk/dist backend/kiosk_dist

tar -czf ~/Documents/parcel-kiosk-deploy.tar.gz \
  --exclude='.venv' --exclude='__pycache__' \
  --exclude='.env' --exclude='*.pyc' \
  --exclude='parcel.db' --exclude='kiosk/node_modules' \
  backend docker-compose.yml
```

**2. 上传到 NAS**

```bash
scp ~/Documents/parcel-kiosk-deploy.tar.gz admin@192.168.3.27:/volume1/
```

**3. NAS SSH 里解压**

```bash
mkdir -p /volume1/docker/parcel-kiosk/data
cd /volume1/docker/parcel-kiosk
tar -xzf /volume1/parcel-kiosk-deploy.tar.gz
```

**4. 创建 .env 文件**

```bash
vi /volume1/docker/parcel-kiosk/backend/.env
```

```env
DINGTALK_APP_KEY=ding3zzaa9ca8wkkwuep
DINGTALK_APP_SECRET=你的Secret
DINGTALK_AGENT_ID=4652995031
SERVER_BASE_URL=http://192.168.3.27:8000
DB_PATH=/data/parcel.db
MAX_SHELVES=2
MAX_LAYERS=4
PRINTER_NAME=_192_168_66_205
```

**5. 启动容器**

```bash
cd /volume1/docker/parcel-kiosk
docker-compose up -d

# 查看日志
docker-compose logs -f

# 验证
curl http://192.168.3.27:8000/health
```

**6. 更新部署**

```bash
# Mac 上重新打包上传后，NAS 上执行：
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## API 接口速查

### 扫码流程

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/scan` | 扫码，创建包裹，分配货架编号 |
| POST | `/scan/{pkg_id}/assign` | 输入手机尾号，匹配员工，发送通知 |

```bash
# 扫码
POST /scan
{"barcode": "SF1234567890123"}
→ {"code": "2-3-0008", "pkg_id": 8, "courier": "顺丰", "status": "need_phone"}

# 匹配
POST /scan/8/assign
{"phone_tail": "3960"}
→ {"status": "matched", "employee_name": "张三"}
→ {"status": "ambiguous_notified", "count": 2}
→ {"status": "unmatched"}
```

### 取件流程

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/pickup/confirm/{pkg_id}` | 取件确认页面（钉钉通知链接） |
| POST | `/pickup/confirm/{pkg_id}` | 确认取件（页面按钮提交） |
| POST | `/pickup/{pkg_id}` | 确认取件（API 调用） |
| GET | `/my-packages?employee_id=xxx` | 查看我的包裹列表（JSON） |

### 待认领

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/unclaimed` | 所有待认领包裹 |
| GET | `/unclaimed/{pkg_id}/review` | 认领审核页面 |
| POST | `/unclaimed/{pkg_id}/review` | 提交认领/拒绝 |

### 员工管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/employees/sync` | 从钉钉同步员工（需手机号读取权限） |
| GET | `/employees/count` | 员工总数 |
| GET | `/employees/by-tail/{tail}` | 手机尾号查员工（工作台登录用） |
| GET | `/auth/dingtalk?code=xxx` | 钉钉免登换 userId |

### 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/workbench` | 员工工作台 H5 页面 |
| GET | `/kiosk` | Kiosk 前端（构建后静态文件） |
| GET | `/health` | 健康检查 + 定时任务状态 |

---

## 环境变量说明

| 变量 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `DINGTALK_APP_KEY` | ✅ | 钉钉应用 Client ID | `ding3zzaa9ca8wkkwuep` |
| `DINGTALK_APP_SECRET` | ✅ | 钉钉应用 Client Secret | `bXo6q...` |
| `DINGTALK_AGENT_ID` | ✅ | 企业内部应用 AgentId | `4652995031` |
| `SERVER_BASE_URL` | ✅ | 后端公开地址（用于推送链接） | `http://192.168.3.27:8000` |
| `DB_PATH` | ❌ | 数据库路径（默认 `parcel.db`） | `/data/parcel.db` |
| `MAX_SHELVES` | ❌ | 货架数量（默认 2） | `3` |
| `MAX_LAYERS` | ❌ | 每架层数（默认 4） | `5` |
| `PRINTER_NAME` | ❌ | CUPS 打印机名 | `_192_168_66_205` |

---

## 日常运维

### 定时任务

| 任务 | 时间 | 说明 |
|------|------|------|
| 员工同步 | 每天 03:00 | 从钉钉同步手机尾号 |
| 催取提醒 | 每天 03:10 | 超 3 天未取推送提醒 |
| 过期清理 | 每天 02:00 | 超 30 天标记为过期 |

### 手动同步员工

```bash
curl -X POST http://192.168.3.27:8000/employees/sync
```

### 查看数据库

```bash
# NAS SSH 里
sqlite3 /volume1/docker/parcel-kiosk/data/parcel.db

SELECT * FROM package WHERE status='pending';           -- 待取包裹
SELECT * FROM employee;                                 -- 员工列表
SELECT count(*) FROM package WHERE status='picked_up'; -- 已取总数
```

### 查看日志

```bash
docker-compose -f /volume1/docker/parcel-kiosk/docker-compose.yml logs --tail=50 -f
```

---

## 常见问题

**Q: 员工同步返回 `synced:0`**
→ 钉钉权限未开通：需开通 `qyapi_get_member`，地址：
`https://open-dev.dingtalk.com/appscope/apply?content=ding3zzaa9ca8wkkwuep#qyapi_get_member`

**Q: 推送通知失败**
→ 检查 `DINGTALK_AGENT_ID` 是否正确；检查应用是否已上线

**Q: 打印机无反应**
→ 确认打印机名：`lpstat -a`；确认 `.env` 里 `PRINTER_NAME` 匹配

**Q: 工作台页面显示"网络错误"**
→ 手机和后端需在同一 WiFi；确认 `SERVER_BASE_URL` 配置正确

**Q: 货架编号一直是 1-1-0001**
→ 检查数据库 `daily_seq` 表；重启后端服务
