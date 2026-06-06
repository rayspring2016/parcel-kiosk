import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine, Session
from main import app
from database import get_session
from models import Employee, Package, PackageStatus


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


def _emp(session, eid, name, tail):
    session.add(Employee(employee_id=eid, name=name, phone_tail=tail))
    session.commit()


def _scan(client, barcode="SF123"):
    with patch("routers.scan.parse_barcode") as m, \
         patch("routers.scan.get_printer_service") as mp:
        m.return_value = MagicMock(courier="顺丰")
        mp.return_value = MagicMock()
        return client.post("/scan", json={"barcode": barcode})


def test_scan_creates_package_immediately(client, session):
    """扫码立即入库并返回编号，无需员工匹配"""
    resp = _scan(client)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "need_phone"
    assert data["code"] == "1-1-0001"
    assert "pkg_id" in data
    # 包裹已在 DB 中，状态为 unclaimed
    pkg = session.get(Package, data["pkg_id"])
    assert pkg is not None
    assert pkg.status == PackageStatus.unclaimed


def test_assign_unique_match(client, session):
    """尾号唯一匹配 → 推送通知，包裹变 pending"""
    _emp(session, "u1", "张三", "8888")
    resp = _scan(client)
    pkg_id = resp.json()["pkg_id"]

    with patch("routers.scan.DingTalkClient") as mock_cls:
        mock_dt = AsyncMock()
        mock_dt.send_pickup_notification.return_value = True
        mock_cls.return_value = mock_dt
        r = client.post(f"/scan/{pkg_id}/assign", json={"phone_tail": "8888"})

    assert r.status_code == 200
    assert r.json()["status"] == "matched"
    assert r.json()["employee_name"] == "张三"
    pkg = session.get(Package, pkg_id)
    assert pkg.status == PackageStatus.pending


def test_assign_ambiguous_needs_surname(client, session):
    """尾号重复 → 要求输入姓氏"""
    _emp(session, "u1", "张三", "1234")
    _emp(session, "u2", "李四", "1234")
    resp = _scan(client)
    pkg_id = resp.json()["pkg_id"]

    r = client.post(f"/scan/{pkg_id}/assign", json={"phone_tail": "1234"})
    assert r.json()["status"] == "ambiguous"
    assert r.json()["count"] == 2


def test_assign_surname_disambiguates(client, session):
    """姓氏消歧成功 → 匹配"""
    _emp(session, "u1", "张三", "1234")
    _emp(session, "u2", "李四", "1234")
    resp = _scan(client)
    pkg_id = resp.json()["pkg_id"]

    with patch("routers.scan.DingTalkClient") as mock_cls:
        mock_dt = AsyncMock()
        mock_dt.send_pickup_notification.return_value = True
        mock_cls.return_value = mock_dt
        r = client.post(f"/scan/{pkg_id}/assign",
                        json={"phone_tail": "1234", "surname": "张"})

    assert r.json()["status"] == "matched"


def test_assign_no_match_stays_unclaimed(client, session):
    """无匹配 → 待认领"""
    resp = _scan(client)
    pkg_id = resp.json()["pkg_id"]

    r = client.post(f"/scan/{pkg_id}/assign", json={"phone_tail": "9999"})
    assert r.json()["status"] == "unmatched"
    pkg = session.get(Package, pkg_id)
    assert pkg.status == PackageStatus.unclaimed


def test_assign_ambiguous_sends_group_push(client, session):
    """姓氏仍重复 → 群发候选人"""
    _emp(session, "u1", "张三", "1234")
    _emp(session, "u2", "张四", "1234")
    resp = _scan(client)
    pkg_id = resp.json()["pkg_id"]

    with patch("routers.scan.DingTalkClient") as mock_cls:
        mock_dt = AsyncMock()
        mock_dt.send_ambiguous_notification.return_value = 2
        mock_cls.return_value = mock_dt
        r = client.post(f"/scan/{pkg_id}/assign",
                        json={"phone_tail": "1234", "surname": "张"})

    assert r.json()["status"] == "unmatched"
    mock_dt.send_ambiguous_notification.assert_called_once()
