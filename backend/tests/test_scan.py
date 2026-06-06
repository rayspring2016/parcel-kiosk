import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine, Session
from main import app
from database import get_session


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
    data = resp.json()
    assert data["matched"] is True
    assert data["slot"] == 1          # 第一个包裹应分配格子 1
    assert data["code"] == "1"


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
    data = resp.json()
    assert data["matched"] is False
    assert data["slot"] == 1
    assert "待认领" in data["code"]
