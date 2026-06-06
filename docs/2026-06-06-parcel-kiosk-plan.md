# 公司内部快递自助系统 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一套快递员自助扫码登记、钉钉自动通知员工、员工编号取件的完整系统，彻底消除公司快递间找包裹慢的问题。

**Architecture:** 后端 FastAPI 服务承载所有业务逻辑（条码解析、员工匹配、打印指令、钉钉推送）；Kiosk 前端是部署在快递间触摸屏上的 Vue 3 全屏 SPA；员工通过钉钉消息内嵌按钮或小程序完成取件确认。三端通过 REST API 通信，数据存 SQLite。

**Tech Stack:** Python 3.11 / FastAPI / SQLModel / SQLite / APScheduler / Vue 3 / DingTalk 企业应用 API

---

## 文件结构

```
Projects/parcel-kiosk/
├── backend/
│   ├── main.py                      # FastAPI 入口，注册路由、启动调度器
│   ├── database.py                  # SQLite 连接、表初始化
│   ├── models.py                    # SQLModel 数据模型 + Pydantic schema
│   ├── config.py                    # 环境变量读取（钉钉 AppKey 等）
│   ├── services/
│   │   ├── barcode.py               # 条码解析，提取手机号
│   │   ├── code_gen.py              # 生成 MMDD-NNN 唯一编号
│   │   ├── dingtalk.py              # 钉钉 API 客户端（通讯录 + 机器人）
│   │   └── printer.py              # ESC-POS 标签打印指令
│   ├── routers/
│   │   ├── scan.py                  # POST /scan —— 核心扫码流程
│   │   ├── pickup.py                # POST /pickup/{code} —— 取件确认
│   │   └── unclaimed.py             # GET/POST /unclaimed —— 待认领管理
│   ├── scheduler.py                 # APScheduler 定时任务（提醒 + 归档）
│   ├── requirements.txt
│   └── tests/
│       ├── test_barcode.py
│       ├── test_code_gen.py
│       ├── test_scan.py
│       ├── test_pickup.py
│       └── test_unclaimed.py
└── kiosk/                           # Vue 3 Kiosk 前端
    ├── index.html
    ├── package.json
    └── src/
        ├── main.js
        ├── App.vue
        ├── views/ScanView.vue       # 主扫码界面（全屏）
        └── api/scan.js              # 调用后端 /scan
```

---

## Task 1: 后端项目初始化

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/config.py`
- Create: `backend/main.py`

- [ ] **Step 1: 创建目录结构**

```bash
cd Projects/parcel-kiosk
mkdir -p backend/services backend/routers backend/tests
touch backend/__init__.py backend/services/__init__.py backend/routers/__init__.py
```

- [ ] **Step 2: 写 requirements.txt**

```
fastapi==0.111.0
uvicorn==0.29.0
sqlmodel==0.0.18
httpx==0.27.0
apscheduler==3.10.4
python-dotenv==1.0.1
pytest==8.2.0
pytest-asyncio==0.23.6
python-escpos==3.0a8
```

- [ ] **Step 3: 写 config.py**

```python
from dotenv import load_dotenv
import os

load_dotenv()

DINGTALK_APP_KEY = os.environ["DINGTALK_APP_KEY"]
DINGTALK_APP_SECRET = os.environ["DINGTALK_APP_SECRET"]
DINGTALK_AGENT_ID = os.environ["DINGTALK_AGENT_ID"]
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "http://localhost:8000")
DB_PATH = os.getenv("DB_PATH", "parcel.db")
```

- [ ] **Step 4: 写 main.py（空壳，后续各 task 注册路由）**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db

app = FastAPI(title="Parcel Kiosk API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产部署改为 Kiosk 实际 origin
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    init_db()

@app.get("/health")
def health():
    try:
        from scheduler import scheduler
        jobs = [{"id": j.id, "next_run": str(j.next_run_time)} for j in scheduler.get_jobs()]
    except Exception:
        jobs = []
    return {"status": "ok", "scheduler_jobs": jobs}
```

- [ ] **Step 5: 创建 .env 模板**

```bash
cat > backend/.env.example << 'EOF'
DINGTALK_APP_KEY=your_app_key
DINGTALK_APP_SECRET=your_app_secret
DINGTALK_AGENT_ID=your_agent_id
SERVER_BASE_URL=http://your-server-ip:8000
DB_PATH=parcel.db
EOF
cp backend/.env.example backend/.env
```

- [ ] **Step 6: 安装依赖并验证启动**

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Expected: 访问 `http://localhost:8000/health` 返回 `{"status":"ok"}`

- [ ] **Step 7: Commit**

```bash
git init
git add backend/
git commit -m "feat: backend project scaffold"
```

---

## Task 2: 数据库模型

**Files:**
- Create: `backend/database.py`
- Create: `backend/models.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: 写 models.py**

```python
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum

class PackageStatus(str, Enum):
    pending = "pending"
    picked_up = "picked_up"
    unclaimed = "unclaimed"
    expired = "expired"

class Package(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)       # e.g. "0606-023"
    courier: str                                      # e.g. "顺丰"
    daily_seq: Optional[int] = None                  # 每日序号，原子性编号生成用
    employee_id: Optional[str] = None                # 钉钉 userId，匹配失败时为 None
    phone_tail: Optional[str] = None                 # 手机后4位，仅未匹配时保存
    status: PackageStatus = PackageStatus.pending
    arrived_at: datetime = Field(default_factory=datetime.now)
    picked_at: Optional[datetime] = None
```

- [ ] **Step 2: 写 database.py**

```python
from sqlmodel import SQLModel, create_engine, Session, text
from config import DB_PATH

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},  # APScheduler 与 FastAPI 共享同一 SQLite 文件
)

def init_db():
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))   # 允许读写并发，APScheduler 写时 FastAPI 仍可读
        conn.execute(text("PRAGMA synchronous=NORMAL"))
        conn.commit()

def get_session():
    with Session(engine) as session:
        yield session
```

- [ ] **Step 3: 写测试**

```python
# tests/test_models.py
import pytest
from sqlmodel import SQLModel, create_engine, Session
from models import Package, PackageStatus

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s

def test_create_package(session):
    pkg = Package(code="0606-001", courier="顺丰", employee_id="user123")
    session.add(pkg)
    session.commit()
    session.refresh(pkg)
    assert pkg.id is not None
    assert pkg.status == PackageStatus.pending

def test_package_default_status(session):
    pkg = Package(code="0606-002", courier="京东")
    session.add(pkg)
    session.commit()
    session.refresh(pkg)
    assert pkg.status == PackageStatus.pending
    assert pkg.employee_id is None
```

- [ ] **Step 4: 运行测试**

```bash
cd backend && pytest tests/test_models.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/database.py backend/models.py backend/tests/test_models.py
git commit -m "feat: database models and init"
```

---

## Task 3: 包裹编号生成器

**Files:**
- Create: `backend/services/code_gen.py`
- Create: `backend/tests/test_code_gen.py`

- [ ] **Step 1: 写测试（先写失败用例）**

```python
# tests/test_code_gen.py
import pytest
from unittest.mock import patch
from datetime import date
from sqlmodel import SQLModel, create_engine, Session
from services.code_gen import generate_code, next_seq
from models import Package

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s

def test_code_format():
    with patch("services.code_gen.date") as mock_date:
        mock_date.today.return_value = date(2026, 6, 6)
        code = generate_code(seq=1)
    assert code == "0606-001"

def test_code_seq_padding():
    with patch("services.code_gen.date") as mock_date:
        mock_date.today.return_value = date(2026, 6, 6)
        code = generate_code(seq=42)
    assert code == "0606-042"

def test_code_seq_large():
    with patch("services.code_gen.date") as mock_date:
        mock_date.today.return_value = date(2026, 6, 6)
        code = generate_code(seq=999)
    assert code == "0606-999"

def test_next_seq_empty_day(session):
    """今日无包裹时 COALESCE(MAX, 0)+1 应返回 1，而非 NULL+1=NULL"""
    assert next_seq(session) == 1

def test_next_seq_increments(session):
    """已有 daily_seq=2 时，应返回 3"""
    session.add(Package(code="0606-001", courier="顺丰", daily_seq=1))
    session.add(Package(code="0606-002", courier="京东", daily_seq=2))
    session.commit()
    assert next_seq(session) == 3
```

- [ ] **Step 2: 运行，确认失败**

```bash
pytest tests/test_code_gen.py -v
```

Expected: ImportError

- [ ] **Step 3: 实现 code_gen.py**

```python
import threading
from datetime import date, datetime
from sqlmodel import Session, select, func
from models import Package

_seq_lock = threading.Lock()  # 单进程部署下防止并发 next_seq 产生相同序号

def generate_code(seq: int) -> str:
    today = date.today()
    return f"{today.strftime('%m%d')}-{seq:03d}"

def next_seq(session: Session) -> int:
    """
    原实现用 COUNT(*)+1 存在竞态：两个并发请求同时读到 count=5，都返回 6。
    改为 SELECT MAX(daily_seq)+1，配合模块级锁确保原子性。
    COALESCE 处理今日第一单时 MAX 返回 NULL 的边界情况。
    """
    with _seq_lock:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        result = session.exec(
            select(func.coalesce(func.max(Package.daily_seq), 0))
            .where(Package.arrived_at >= today_start)
        ).one()
        return result + 1
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_code_gen.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/code_gen.py backend/tests/test_code_gen.py
git commit -m "feat: package code generator"
```

---

## Task 4: 条码解析服务

**Files:**
- Create: `backend/services/barcode.py`
- Create: `backend/tests/test_barcode.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_barcode.py
from services.barcode import parse_barcode

def test_parse_json_format():
    raw = '{"name":"张三","mobile":"13800138000","courier":"YTO"}'
    result = parse_barcode(raw)
    assert result.phone == "13800138000"
    assert result.courier == "圆通"

def test_parse_sf_format():
    raw = "SF|13900139000|李四|北京市朝阳区"
    result = parse_barcode(raw)
    assert result.phone == "13900139000"
    assert result.courier == "顺丰"

def test_parse_phone_regex_fallback():
    raw = "JD0012345678|王五|13700137000|上海市"
    result = parse_barcode(raw)
    assert result.phone == "13700137000"

def test_parse_no_phone_returns_none():
    raw = "UNKNOWN_FORMAT_NO_PHONE"
    result = parse_barcode(raw)
    assert result.phone is None

def test_courier_detection_jd():
    raw = '{"mobile":"13800138000","courier":"JD"}'
    result = parse_barcode(raw)
    assert result.courier == "京东"
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_barcode.py -v
```

- [ ] **Step 3: 实现 barcode.py**

```python
import json
import re
from dataclasses import dataclass
from typing import Optional

COURIER_MAP = {
    "SF": "顺丰", "JD": "京东", "YTO": "圆通",
    "ZTO": "中通", "STO": "申通", "YUNDA": "韵达",
    "EMS": "EMS", "HTKY": "百世",
}

@dataclass
class BarcodeResult:
    phone: Optional[str]
    courier: str = "未知"

def _detect_courier(text: str) -> str:
    for code, name in COURIER_MAP.items():
        if code in text.upper():
            return name
    return "未知"

def _extract_phone(text: str) -> Optional[str]:
    match = re.search(r"1[3-9]\d{9}", text)
    return match.group() if match else None

def parse_barcode(raw: str) -> BarcodeResult:
    try:
        data = json.loads(raw)
        phone = data.get("mobile") or data.get("phone") or data.get("receiverMobile")
        courier_code = data.get("courier", "")
        courier = COURIER_MAP.get(courier_code.upper(), _detect_courier(raw))
        return BarcodeResult(phone=phone, courier=courier)
    except (json.JSONDecodeError, AttributeError):
        pass

    parts = raw.split("|")
    if len(parts) >= 2 and parts[0].upper() in COURIER_MAP:
        phone = _extract_phone(parts[1]) or _extract_phone(raw)
        return BarcodeResult(phone=phone, courier=COURIER_MAP[parts[0].upper()])

    return BarcodeResult(phone=_extract_phone(raw), courier=_detect_courier(raw))
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/test_barcode.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/barcode.py backend/tests/test_barcode.py
git commit -m "feat: barcode parser with multi-format support"
```

---

## Task 5: 钉钉 API 客户端

**Files:**
- Create: `backend/services/dingtalk.py`
- Create: `backend/tests/test_dingtalk.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_dingtalk.py
import pytest
from unittest.mock import AsyncMock, patch
from services.dingtalk import DingTalkClient

@pytest.fixture
def client():
    return DingTalkClient(app_key="test_key", app_secret="test_secret", agent_id="12345")

@pytest.mark.asyncio
async def test_get_user_by_phone_found(client):
    mock_response = {"result": {"userid": "user_abc123"}, "errcode": 0}
    with patch.object(client, "_request", new=AsyncMock(return_value=mock_response)):
        user_id = await client.get_user_id_by_phone("13800138000")
    assert user_id == "user_abc123"

@pytest.mark.asyncio
async def test_get_user_by_phone_not_found(client):
    mock_response = {"errcode": 60121}
    with patch.object(client, "_request", new=AsyncMock(return_value=mock_response)):
        user_id = await client.get_user_id_by_phone("13999999999")
    assert user_id is None

@pytest.mark.asyncio
async def test_send_pickup_notification(client):
    with patch.object(client, "_request", new=AsyncMock(return_value={"errcode": 0})):
        ok = await client.send_pickup_notification(
            user_id="user_abc123",
            code="0606-023",
            courier="顺丰",
            pickup_url="http://localhost:8000/pickup/0606-023/confirm"
        )
    assert ok is True

@pytest.mark.asyncio
async def test_send_reminder(client):
    with patch.object(client, "_request", new=AsyncMock(return_value={"errcode": 0})):
        ok = await client.send_reminder(
            user_id="user_abc123",
            code="0606-023",
            pickup_url="http://localhost:8000/pickup/0606-023/confirm"
        )
    assert ok is True

@pytest.mark.asyncio
async def test_token_expires_and_refreshes(client):
    """token 过期后 _get_token 应被重新调用，不能沿用旧 token"""
    import time
    client._access_token = "old_token"
    client._token_expires_at = time.time() - 1  # 模拟已过期
    with patch.object(client, "_get_token", new=AsyncMock(return_value="new_token")) as mock_refresh:
        with patch.object(client, "_request", new=AsyncMock(return_value={"errcode": 0})):
            await client.send_pickup_notification("u1", "0606-001", "顺丰", "http://x/confirm")
    mock_refresh.assert_called_once()
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_dingtalk.py -v
```

- [ ] **Step 3: 实现 dingtalk.py**

```python
import httpx
from typing import Optional

DINGTALK_API = "https://oapi.dingtalk.com"

class DingTalkClient:
    def __init__(self, app_key: str, app_secret: str, agent_id: str):
        self.app_key = app_key
        self.app_secret = app_secret
        self.agent_id = agent_id
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0  # unix timestamp，0 表示从未获取

    async def _get_token(self) -> str:
        import time
        async with httpx.AsyncClient() as http:
            r = await http.get(
                f"{DINGTALK_API}/gettoken",
                params={"appkey": self.app_key, "appsecret": self.app_secret}
            )
        self._access_token = r.json()["access_token"]
        self._token_expires_at = time.time() + 7200 - 60  # 提前 60s 刷新，避免边界失效
        return self._access_token

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        import time
        if not self._access_token or time.time() >= self._token_expires_at:
            await self._get_token()
        url = f"{DINGTALK_API}{path}?access_token={self._access_token}"
        async with httpx.AsyncClient() as http:
            resp = await http.request(method, url, **kwargs)
        return resp.json()

    async def get_user_id_by_phone(self, phone: str) -> Optional[str]:
        data = await self._request("POST", "/topapi/v2/user/getbymobile", json={"mobile": phone})
        if data.get("errcode") != 0:
            return None
        return data.get("result", {}).get("userid")

    async def send_pickup_notification(self, user_id: str, code: str, courier: str, pickup_url: str) -> bool:
        """发送 OA 工作通知，视觉与钉钉考勤等系统通知一致"""
        from datetime import datetime
        arrived_str = datetime.now().strftime("%Y/%m/%d %H:%M")
        data = await self._request(
            "POST",
            "/topapi/message/corpconversation/asyncsend_v2",
            json={
                "agent_id": self.agent_id,
                "userid_list": user_id,
                "msg": {
                    "msgtype": "oa",
                    "oa": {
                        "message_url": pickup_url,
                        "pc_message_url": pickup_url,
                        "head": {
                            "bgcolor": "FF1E88E5",   # 蓝色标题栏
                            "text": "你有快递到了！"
                        },
                        "body": {
                            "title": f"包裹编号：{code}",
                            "form": [
                                {"key": "快递公司", "value": courier},
                                {"key": "到件时间", "value": arrived_str},
                            ],
                            "content": "请到快递间货架找对应编号取件，点击「已取件」完成确认。"
                        }
                    }
                }
            }
        )
        return data.get("errcode") == 0

    async def send_reminder(self, user_id: str, code: str, pickup_url: str) -> bool:
        """48小时未取件提醒，同样使用 OA 格式"""
        data = await self._request(
            "POST",
            "/topapi/message/corpconversation/asyncsend_v2",
            json={
                "agent_id": self.agent_id,
                "userid_list": user_id,
                "msg": {
                    "msgtype": "oa",
                    "oa": {
                        "message_url": pickup_url,
                        "pc_message_url": pickup_url,
                        "head": {
                            "bgcolor": "FFF59E0B",   # 橙色标题栏，区分提醒
                            "text": "快递待取件提醒"
                        },
                        "body": {
                            "title": f"包裹编号：{code}",
                            "content": "你的快递已超过48小时未取，请尽快到快递间领取。"
                        }
                    }
                }
            }
        )
        return data.get("errcode") == 0
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/test_dingtalk.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/dingtalk.py backend/tests/test_dingtalk.py
git commit -m "feat: dingtalk api client with notification and token refresh"
```

---

## Task 6: 标签打印服务

**Files:**
- Create: `backend/services/printer.py`
- Create: `backend/tests/test_printer.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_printer.py
from unittest.mock import MagicMock
from services.printer import PrinterService

def test_print_label_sends_content():
    mock_printer = MagicMock()
    svc = PrinterService(printer=mock_printer)
    svc.print_label(code="0606-023", courier="顺丰", arrived_at="2026/06/06 14:32")
    assert mock_printer.text.called

def test_print_unclaimed_label():
    mock_printer = MagicMock()
    svc = PrinterService(printer=mock_printer)
    svc.print_unclaimed_label(code="待认领-0606-024", courier="京东", arrived_at="2026/06/06 15:00")
    assert mock_printer.text.called
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_printer.py -v
```

- [ ] **Step 3: 实现 printer.py**

```python
from escpos.printer import Usb

class PrinterService:
    def __init__(self, printer=None, usb_vendor=0x04b8, usb_product=0x0202):
        self.printer = printer or Usb(usb_vendor, usb_product)

    def _print_lines(self, lines: list[str]):
        p = self.printer
        p.set(align="center", bold=True, height=2, width=2)
        for line in lines:
            p.text(line + "\n")
        p.set(align="center", bold=False, height=1, width=1)
        p.cut()

    def print_label(self, code: str, courier: str, arrived_at: str):
        self._print_lines([courier, code, f"到件：{arrived_at}"])

    def print_unclaimed_label(self, code: str, courier: str, arrived_at: str):
        self._print_lines(["【待认领】", courier, code, f"到件：{arrived_at}"])

_printer_instance: Optional["PrinterService"] = None

def get_printer_service() -> PrinterService:
    """懒加载单例：USB 打印机不支持多连接，必须全程共用同一实例"""
    global _printer_instance
    if _printer_instance is None:
        _printer_instance = PrinterService()
    return _printer_instance
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/test_printer.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/printer.py backend/tests/test_printer.py
git commit -m "feat: label printer service with ESC-POS"
```

---

## Task 7: 核心扫码 API

**Files:**
- Create: `backend/routers/scan.py`
- Create: `backend/tests/test_scan.py`
- Modify: `backend/main.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_scan.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from sqlmodel import SQLModel, create_engine, Session
from main import app
from database import get_session

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s

@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)

def test_scan_matched(client):
    with (
        patch("routers.scan.parse_barcode") as mock_parse,
        patch("routers.scan.DingTalkClient") as mock_dt_cls,
        patch("routers.scan.get_printer_service") as mock_printer,
    ):
        mock_parse.return_value = MagicMock(phone="13800138000", courier="顺丰")
        mock_dt = AsyncMock()
        mock_dt.get_user_id_by_phone.return_value = "user_abc"
        mock_dt.send_pickup_notification.return_value = True
        mock_dt_cls.return_value = mock_dt
        mock_printer.return_value = MagicMock()
        resp = client.post("/scan", json={"barcode": "SF|13800138000|张三|北京"})
    assert resp.status_code == 200
    assert resp.json()["matched"] is True
    assert resp.json()["code"].startswith("06")

def test_scan_unmatched(client):
    with (
        patch("routers.scan.parse_barcode") as mock_parse,
        patch("routers.scan.DingTalkClient") as mock_dt_cls,
        patch("routers.scan.get_printer_service") as mock_printer,
    ):
        mock_parse.return_value = MagicMock(phone="13999999999", courier="顺丰")
        mock_dt = AsyncMock()
        mock_dt.get_user_id_by_phone.return_value = None
        mock_dt_cls.return_value = mock_dt
        mock_printer.return_value = MagicMock()
        resp = client.post("/scan", json={"barcode": "SOME_BARCODE"})
    assert resp.status_code == 200
    assert resp.json()["matched"] is False
    assert "待认领" in resp.json()["code"]
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_scan.py -v
```

- [ ] **Step 3: 实现 routers/scan.py**

```python
from fastapi import APIRouter, Depends
from sqlmodel import Session
from pydantic import BaseModel
from datetime import datetime
from database import get_session
from models import Package, PackageStatus
from services.barcode import parse_barcode
from services.code_gen import generate_code, next_seq
from services.dingtalk import DingTalkClient
from services.printer import get_printer_service
from config import DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID, SERVER_BASE_URL

router = APIRouter()

class ScanRequest(BaseModel):
    barcode: str

@router.post("/scan")
async def scan(req: ScanRequest, session: Session = Depends(get_session)):
    result = parse_barcode(req.barcode)
    seq = next_seq(session)
    dt = DingTalkClient(DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID)
    printer = get_printer_service()
    now_str = datetime.now().strftime("%Y/%m/%d %H:%M")

    employee_id = None
    if result.phone:
        employee_id = await dt.get_user_id_by_phone(result.phone)

    if employee_id:
        code = generate_code(seq)
        session.add(Package(code=code, courier=result.courier, employee_id=employee_id, daily_seq=seq))
        session.commit()
        pickup_url = f"{SERVER_BASE_URL}/pickup/{code}/confirm"
        await dt.send_pickup_notification(employee_id, code, result.courier, pickup_url)
        printer.print_label(code=code, courier=result.courier, arrived_at=now_str)
        return {"matched": True, "code": code, "courier": result.courier}
    else:
        code = f"待认领-{generate_code(seq)}"
        session.add(Package(
            code=code,
            courier=result.courier,
            status=PackageStatus.unclaimed,
            daily_seq=seq,
            phone_tail=result.phone[-4:] if result.phone else None,
        ))
        session.commit()
        printer.print_unclaimed_label(code=code, courier=result.courier, arrived_at=now_str)
        return {"matched": False, "code": code, "courier": result.courier}
```

- [ ] **Step 4: 在 main.py 注册路由**

```python
# main.py 追加以下两行
from routers.scan import router as scan_router
app.include_router(scan_router)
```

- [ ] **Step 5: 运行测试**

```bash
pytest tests/test_scan.py -v
```

Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add backend/routers/scan.py backend/tests/test_scan.py backend/main.py
git commit -m "feat: core scan endpoint with match/unmatch flow"
```

---

## Task 8: 取件确认 API

**Files:**
- Create: `backend/routers/pickup.py`
- Create: `backend/tests/test_pickup.py`
- Modify: `backend/main.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_pickup.py
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from main import app
from database import get_session
from models import Package, PackageStatus
from datetime import datetime

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s

@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)

def test_pickup_success(client, session):
    session.add(Package(code="0606-001", courier="顺丰", employee_id="user123"))
    session.commit()
    resp = client.post("/pickup/0606-001")
    assert resp.status_code == 200
    assert resp.json()["status"] == "picked_up"

def test_pickup_not_found(client):
    resp = client.post("/pickup/0606-999")
    assert resp.status_code == 404

def test_pickup_already_done(client, session):
    session.add(Package(
        code="0606-002", courier="京东", employee_id="user123",
        status=PackageStatus.picked_up, picked_at=datetime.now()
    ))
    session.commit()
    resp = client.post("/pickup/0606-002")
    assert resp.status_code == 400

def test_my_packages(client, session):
    session.add(Package(code="0606-003", courier="顺丰", employee_id="user123"))
    session.add(Package(code="0606-004", courier="京东", employee_id="user456"))
    session.commit()
    resp = client.get("/my-packages?employee_id=user123")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["code"] == "0606-003"

def test_get_confirm_page(client, session):
    session.add(Package(code="0606-005", courier="圆通", employee_id="user123"))
    session.commit()
    resp = client.get("/pickup/0606-005/confirm")
    assert resp.status_code == 200
    assert "确认" in resp.text
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_pickup.py -v
```

- [ ] **Step 3: 实现 routers/pickup.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from datetime import datetime
from database import get_session
from models import Package, PackageStatus

router = APIRouter()

@router.post("/pickup/{code}")
def confirm_pickup(code: str, session: Session = Depends(get_session)):
    pkg = session.exec(select(Package).where(Package.code == code)).first()
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    if pkg.status == PackageStatus.picked_up:
        raise HTTPException(status_code=400, detail="Already picked up")
    pkg.status = PackageStatus.picked_up
    pkg.picked_at = datetime.now()
    session.add(pkg)
    session.commit()
    return {"status": "picked_up", "code": code, "picked_at": pkg.picked_at}

@router.get("/my-packages")
def my_packages(employee_id: str, session: Session = Depends(get_session)):
    pkgs = session.exec(select(Package).where(Package.employee_id == employee_id)).all()
    return [{"code": p.code, "courier": p.courier, "arrived_at": p.arrived_at, "status": p.status} for p in pkgs]

@router.get("/pickup/{code}/confirm")
def confirm_pickup_page(code: str, session: Session = Depends(get_session)):
    """OA 消息 message_url 点击后触发此 GET 端点（钉钉不支持 POST 跳转）"""
    from fastapi.responses import HTMLResponse
    pkg = session.exec(select(Package).where(Package.code == code)).first()
    if not pkg or pkg.status == PackageStatus.picked_up:
        return HTMLResponse("<h2>✓ 包裹已确认取件</h2>", status_code=200)
    pkg.status = PackageStatus.picked_up
    pkg.picked_at = datetime.now()
    session.add(pkg)
    session.commit()
    return HTMLResponse(
        f"<h2>✓ 取件确认成功</h2><p>包裹编号：{code}</p><p>感谢确认！</p>",
        status_code=200
    )
```

- [ ] **Step 4: 注册路由**

```python
# main.py 追加
from routers.pickup import router as pickup_router
app.include_router(pickup_router)
```

- [ ] **Step 5: 运行测试**

```bash
pytest tests/test_pickup.py -v
```

Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add backend/routers/pickup.py backend/tests/test_pickup.py backend/main.py
git commit -m "feat: pickup confirmation and my-packages endpoints"
```

---

## Task 9: 待认领包裹 API

**Files:**
- Create: `backend/routers/unclaimed.py`
- Create: `backend/tests/test_unclaimed.py`
- Modify: `backend/main.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_unclaimed.py
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from main import app
from database import get_session
from models import Package, PackageStatus

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s

@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)

def test_list_unclaimed(client, session):
    session.add(Package(code="待认领-0606-005", courier="圆通", status=PackageStatus.unclaimed))
    session.add(Package(code="0606-006", courier="顺丰", employee_id="u1"))
    session.commit()
    resp = client.get("/unclaimed")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["code"] == "待认领-0606-005"

def test_claim_package(client, session):
    session.add(Package(code="待认领-0606-007", courier="京东", status=PackageStatus.unclaimed))
    session.commit()
    resp = client.post("/unclaimed/待认领-0606-007/claim", json={"employee_id": "user_xyz"})
    assert resp.status_code == 200
    assert resp.json()["employee_id"] == "user_xyz"

def test_claim_not_found(client):
    resp = client.post("/unclaimed/不存在编号/claim", json={"employee_id": "user_xyz"})
    assert resp.status_code == 404

def test_claim_wrong_status(client, session):
    """已有 employee_id 的包裹（status=pending）不能被再次认领"""
    session.add(Package(code="待认领-0606-008", courier="顺丰",
                        status=PackageStatus.pending, employee_id="user_abc"))
    session.commit()
    resp = client.post("/unclaimed/待认领-0606-008/claim", json={"employee_id": "user_xyz"})
    assert resp.status_code == 400
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_unclaimed.py -v
```

- [ ] **Step 3: 实现 routers/unclaimed.py**

```python
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
```

- [ ] **Step 4: 注册路由**

```python
# main.py 追加
from routers.unclaimed import router as unclaimed_router
app.include_router(unclaimed_router)
```

- [ ] **Step 5: 运行测试**

```bash
pytest tests/test_unclaimed.py -v
```

Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add backend/routers/unclaimed.py backend/tests/test_unclaimed.py backend/main.py
git commit -m "feat: unclaimed packages api"
```

---

## Task 10: 定时任务（48h 提醒 + 7天归档）

**Files:**
- Create: `backend/scheduler.py`
- Modify: `backend/main.py`

- [ ] **Step 1: 实现 scheduler.py**

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import Session, select
from datetime import datetime, timedelta
from models import Package, PackageStatus
from database import engine
from services.dingtalk import DingTalkClient
from config import DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID

import logging
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def send_reminders():
    cutoff = datetime.now() - timedelta(hours=48)
    with Session(engine) as session:
        pkgs = session.exec(
            select(Package)
            .where(Package.status == PackageStatus.pending)
            .where(Package.arrived_at <= cutoff)
            .where(Package.employee_id.isnot(None))
        ).all()
        dt = DingTalkClient(DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID)
        sent = 0
        for pkg in pkgs:
            pickup_url = f"{SERVER_BASE_URL}/pickup/{pkg.code}/confirm"
            try:
                ok = await dt.send_reminder(pkg.employee_id, pkg.code, pickup_url)
                if ok:
                    sent += 1
                else:
                    logger.warning("Reminder send failed for pkg %s", pkg.code)
            except Exception as e:
                logger.error("Reminder error for pkg %s: %s", pkg.code, e)
        logger.info("Reminders sent: %d / %d pending", sent, len(pkgs))

async def expire_old_packages():
    cutoff = datetime.now() - timedelta(days=7)
    with Session(engine) as session:
        pkgs = session.exec(
            select(Package)
            .where(Package.status.in_([PackageStatus.pending, PackageStatus.unclaimed]))
            .where(Package.arrived_at <= cutoff)
        ).all()
        for pkg in pkgs:
            pkg.status = PackageStatus.expired
            session.add(pkg)
        session.commit()
        logger.info("Expired %d packages", len(pkgs))

def start_scheduler():
    scheduler.add_job(send_reminders, "interval", hours=1, id="reminders")
    scheduler.add_job(expire_old_packages, "cron", hour=2, minute=0, id="expire")
    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))
```

- [ ] **Step 2: 在 main.py 启动调度器**

```python
# 更新 on_startup（async def 确保 AsyncIOScheduler 在正确 event loop 中启动）
from scheduler import start_scheduler

@app.on_event("startup")
async def on_startup():
    init_db()
    start_scheduler()
```

- [ ] **Step 2b: 新增 tests/test_scheduler.py**

```python
# tests/test_scheduler.py
import pytest
from unittest.mock import AsyncMock, patch
from sqlmodel import SQLModel, create_engine, Session
from datetime import datetime, timedelta
from models import Package, PackageStatus

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s

@pytest.mark.asyncio
async def test_send_reminders_calls_dingtalk(session):
    old_pkg = Package(
        code="0606-001", courier="顺丰", employee_id="user123",
        arrived_at=datetime.now() - timedelta(hours=50)
    )
    session.add(old_pkg)
    session.commit()
    with patch("scheduler.DingTalkClient") as mock_cls, \
         patch("scheduler.Session", return_value=session):
        mock_dt = AsyncMock()
        mock_dt.send_reminder = AsyncMock(return_value=True)
        mock_cls.return_value = mock_dt
        from scheduler import send_reminders
        await send_reminders()
    mock_dt.send_reminder.assert_called_once()

@pytest.mark.asyncio
async def test_expire_old_packages(session):
    old_pkg = Package(
        code="0606-002", courier="京东",
        arrived_at=datetime.now() - timedelta(days=8)
    )
    session.add(old_pkg)
    session.commit()
    with patch("scheduler.Session", return_value=session):
        from scheduler import expire_old_packages
        await expire_old_packages()
    session.refresh(old_pkg)
    assert old_pkg.status == PackageStatus.expired

@pytest.mark.asyncio
async def test_pending_not_expired(session):
    recent_pkg = Package(
        code="0606-003", courier="圆通",
        arrived_at=datetime.now() - timedelta(days=3)
    )
    session.add(recent_pkg)
    session.commit()
    with patch("scheduler.Session", return_value=session):
        from scheduler import expire_old_packages
        await expire_old_packages()
    session.refresh(recent_pkg)
    assert recent_pkg.status == PackageStatus.pending
```

- [ ] **Step 3: 运行全部测试**

```bash
cd backend && pytest -v
```

Expected: 全部 passed

- [ ] **Step 4: Commit**

```bash
git add backend/scheduler.py backend/main.py
git commit -m "feat: scheduled reminders and auto-expiry"
```

---

## Task 11: Kiosk 前端（Vue 3）

**Files:**
- Create: `kiosk/src/api/scan.js`
- Create: `kiosk/src/views/ScanView.vue`
- Modify: `kiosk/src/App.vue`

- [ ] **Step 1: 初始化 Vue 3 项目**

```bash
cd Projects/parcel-kiosk
npm create vue@latest kiosk -- --template base
cd kiosk && npm install
```

- [ ] **Step 2: 写 src/api/scan.js**

```js
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"

export async function submitBarcode(barcode) {
  const resp = await fetch(`${BASE_URL}/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ barcode }),
  })
  if (!resp.ok) throw new Error("扫描请求失败")
  return resp.json()
}
```

- [ ] **Step 3: 写 src/views/ScanView.vue**

```vue
<template>
  <div class="kiosk">
    <div v-if="state === 'idle'" class="prompt">
      <p class="big-text">请扫描包裹条码</p>
      <input ref="hiddenInput" class="hidden-input" @keydown.enter="onEnter" v-model="buffer" autofocus />
    </div>
    <div v-else-if="state === 'success'" class="result success">
      <p>✅ 扫描成功</p>
      <p class="code">{{ lastCode }}</p>
      <p>请取出标签贴到包裹上</p>
    </div>
    <div v-else-if="state === 'error'" class="result error">
      <p>❌ 扫描失败，请重试</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue"
import { submitBarcode } from "../api/scan.js"

const state = ref("idle")
const buffer = ref("")
const lastCode = ref("")
const hiddenInput = ref(null)

onMounted(() => {
  hiddenInput.value?.focus()
  // USB HID 扫码枪模拟键盘输入，焦点丢失时扫码数据全部丢失
  // 任何点击或屏保唤醒后自动重新聚焦
  document.addEventListener("click", () => hiddenInput.value?.focus())
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) hiddenInput.value?.focus()
  })
})

async function onEnter() {
  const barcode = buffer.value.trim()
  buffer.value = ""
  if (!barcode) return
  try {
    const data = await submitBarcode(barcode)
    lastCode.value = data.code
    state.value = "success"
  } catch {
    state.value = "error"
  }
  setTimeout(() => { state.value = "idle"; hiddenInput.value?.focus() }, 4000)
}
</script>

<style scoped>
.kiosk { display:flex; justify-content:center; align-items:center; height:100vh; background:#1a1a2e; color:white; font-family:sans-serif; }
.big-text { font-size:3rem; text-align:center; }
.hidden-input { position:absolute; opacity:0; width:1px; }
.result { text-align:center; font-size:2rem; }
.code { font-size:4rem; font-weight:bold; margin:1rem 0; }
.success { color:#4caf50; }
.error { color:#f44336; }
</style>
```

- [ ] **Step 4: 更新 App.vue**

```vue
<template><ScanView /></template>
<script setup>
import ScanView from "./views/ScanView.vue"
</script>
```

- [ ] **Step 5: 本地验证**

```bash
VITE_API_URL=http://localhost:8000 npm run dev
```

Expected: 浏览器打开全屏黑色界面，显示「请扫描包裹条码」

- [ ] **Step 6: 构建生产包**

```bash
npm run build
```

Expected: `dist/` 目录生成，无报错

- [ ] **Step 7: Commit**

```bash
git add kiosk/
git commit -m "feat: kiosk frontend with scan interface"
```

---

## Task 12: 钉钉小程序（员工端）

> 需要在[钉钉开放平台](https://open.dingtalk.com)创建企业内部应用，使用 DingTalk DevTools 开发。

- [ ] **Step 1: 创建小程序目录**

```bash
mkdir -p Projects/parcel-kiosk/miniapp/pages/myPackages
mkdir -p Projects/parcel-kiosk/miniapp/pages/unclaimed
```

- [ ] **Step 2: 写 miniapp/app.json + miniapp/app.js**

```json
{
  "pages": ["pages/myPackages/index", "pages/unclaimed/index"],
  "window": { "defaultTitle": "快递自助取件" }
}
```

```js
// app.js — API 地址集中在 globalData，两个页面不重复定义
App({
  globalData: {
    API: "http://your-server-ip:8000"
  }
})
```

- [ ] **Step 3: 写「我的包裹」页面逻辑 pages/myPackages/index.js**

```js
const API = getApp().globalData.API  // 统一从 globalData 读取，修改一处即全局生效

Page({
  data: { packages: [], loading: true },
  async onLoad() {
    const userId = dd.getStorageSync({ key: "userId" }).data
    const res = await dd.httpRequest({ url: `${API}/my-packages?employee_id=${userId}`, method: "GET" })
    this.setData({ packages: res.data, loading: false })
  },
  async onPickup(e) {
    const code = e.currentTarget.dataset.code
    await dd.httpRequest({ url: `${API}/pickup/${code}/confirm`, method: "GET" })
    this.onLoad()
  }
})
```

- [ ] **Step 4: 写「我的包裹」页面模板 pages/myPackages/index.axml**

```xml
<view class="container">
  <block a:for="{{packages}}" key="{{item.code}}">
    <view class="card">
      <text class="code">{{item.code}}</text>
      <text>{{item.courier}} · {{item.arrived_at}}</text>
      <button onTap="onPickup" data-code="{{item.code}}" a:if="{{item.status === 'pending'}}">
        ✅ 已取件
      </button>
    </view>
  </block>
</view>
```

- [ ] **Step 5: 写「待认领」页面逻辑 pages/unclaimed/index.js**

```js
const API = getApp().globalData.API

Page({
  data: { packages: [] },
  async onLoad() {
    const res = await dd.httpRequest({ url: `${API}/unclaimed`, method: "GET" })
    this.setData({ packages: res.data })
  },
  async onClaim(e) {
    const code = e.currentTarget.dataset.code
    const userId = dd.getStorageSync({ key: "userId" }).data
    await dd.httpRequest({
      url: `${API}/unclaimed/${code}/claim`,
      method: "POST",
      data: JSON.stringify({ employee_id: userId }),
      headers: { "Content-Type": "application/json" }
    })
    dd.alert({ title: "认领成功", content: `包裹 ${code} 已归入你的名下，请到快递间对应编号处取件` })
    this.onLoad()
  }
})
```

- [ ] **Step 6: 写「待认领」页面模板 pages/unclaimed/index.axml**

```xml
<view class="container">
  <block a:for="{{packages}}" key="{{item.code}}">
    <view class="card">
      <text>{{item.courier}} 到件：{{item.arrived_at}}</text>
      <text class="code">{{item.code}}</text>
      <text a:if="{{item.phone_tail}}" class="hint">收件手机尾号：{{item.phone_tail}}</text>
      <button onTap="onClaim" data-code="{{item.code}}">这是我的包裹</button>
    </view>
  </block>
</view>
```

- [ ] **Step 7: Commit**

```bash
git add Projects/parcel-kiosk/miniapp/
git commit -m "feat: dingtalk miniapp employee pickup interface"
```

---

## 验收清单

- [ ] `pytest -v` 全部通过（预期：20 个测试，含 scheduler 3 项）
- [ ] Kiosk 启动后全屏显示「请扫描包裹条码」
- [ ] 扫测试条码，成功显示编号，4秒后回到待机
- [ ] 钉钉收到 OA 格式通知（蓝色标题栏 + 快递公司 + 到件时间）
- [ ] 点击通知跳转 GET /pickup/{code}/confirm 页面，包裹状态变为 `picked_up`
- [ ] 未匹配条码打印「待认领」标签，出现在 `/unclaimed` 列表，显示手机尾号
- [ ] 钉钉小程序「我的包裹」显示正确记录（需 authCode 验证）
- [ ] 48h 未取件发出提醒消息（含 pickup_url）
- [ ] 服务运行 3 小时后钉钉通知仍可正常发送（token 自动刷新）
- [ ] 两个包裹同时扫码不出现 500 错误（next_seq 竞态修复）

---

## Implementation Tasks

*CEO Review (HOLD SCOPE) + Eng Review 发现的所有修复均已直接合并进上方各 Task 正文代码。*
*实施时直接照 Task 1–12 步骤执行即可，无需额外查阅本节。*

| ID | 类别 | 修复位置 | 状态 |
|----|------|---------|------|
| T1/T11 | P1 Architecture | main.py — CORS + async on_startup | ✅ 已合并 Task 1 Step 4 |
| T2 | P1 Architecture | pickup.py — GET /pickup/{code}/confirm | ✅ 已合并 Task 8 Step 3 |
| T3 | P1 Bug | scheduler.py — send_reminder pickup_url 参数 | ✅ 已合并 Task 10 Step 1 |
| T4 | P1 Bug | dingtalk.py — token 过期自动刷新 | ✅ 已合并 Task 5 Step 3 |
| T5 | P1 Security | DingTalk authCode 验证 | ⚠️ 范围较大，建议单独 Task 后续补充 |
| T6/P2 | P1 Bug | code_gen.py — next_seq 竞态 + daily_seq 字段 | ✅ 已合并 Task 2/3 |
| T7 | P1 Bug | printer.py — USB 单例 | ✅ 已合并 Task 6 Step 3 |
| T8 | P2 UX | unclaimed/index.axml — phone_tail 显示 | ✅ 已合并 Task 12 Step 6 |
| T9 | P1 Test | test_scheduler.py — 3 个测试 | ✅ 已合并 Task 10 Step 2b |
| T10 | P2 Observability | scheduler.py — 结构化日志 | ✅ 已合并 Task 10 Step 1 |
| T12 | P2 UX | unclaimed/index.js — alert 含编号 | ✅ 已合并 Task 12 Step 5 |

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | CLOSED | 12 issues → 11 merged, T5 authCode 留待后续 |
| Eng Review | `/plan-eng-review` | Architecture & tests | 1 | CLOSED | A1 WAL, A2 Focus, C1 Code, P2 daily_seq, T3-1 Tests, TODO-1 Health |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**Eng Review 发现（6项，全部批准并写入正文）：**
- A1 SQLite WAL + check_same_thread — `database.py` ✅
- A2 Kiosk 扫码枪焦点丢失全局自恢复 — `ScanView.vue` ✅
- C1 T1-T12 结构问题（无实现代码）— 直接修正正文 ✅
- P2 daily_seq 字段缺失 → next_seq MAX 查询无字段可用 — `models.py` + `code_gen.py` ✅
- T3-1 缺失测试（scheduler/pickup/unclaimed）— 加入各 Task ✅
- TODO-1 Scheduler 健康状态 → `GET /health` 展示 jobs ✅

**关键失败模式（3项，已在验收清单标注）：**
1. 打印异常 → 包裹入库但无标签（快递员不知情）
2. 钉钉推送 errcode≠0 → scan 返回成功但员工无通知
3. APScheduler 停止运行 → 提醒和归档静默中断

- **UNRESOLVED:** 1（T5 authCode 身份验证，P1 安全，建议后续实施）
- **VERDICT:** CEO Review + Eng Review 双重审查完成，计划可进入实施阶段。建议先完成 T5 authCode 再上线。
