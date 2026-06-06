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
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
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
    resp = _scan(client)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "need_phone"
    assert data["code"] == "1-1-0001"
    pkg = session.get(Package, data["pkg_id"])
    assert pkg.status == PackageStatus.unclaimed


def test_assign_unique_match(client, session):
    _emp(session, "u1", "张三", "8888")
    pkg_id = _scan(client).json()["pkg_id"]

    with patch("routers.scan.DingTalkClient") as mock_cls:
        mock_dt = AsyncMock()
        mock_dt.send_pickup_notification.return_value = True
        mock_cls.return_value = mock_dt
        r = client.post(f"/scan/{pkg_id}/assign", json={"phone_tail": "8888"})

    assert r.json() == {"status": "matched", "employee_name": "张三"}
    assert session.get(Package, pkg_id).status == PackageStatus.pending


def test_assign_duplicate_notifies_all(client, session):
    _emp(session, "u1", "张三", "1234")
    _emp(session, "u2", "李四", "1234")
    pkg_id = _scan(client).json()["pkg_id"]

    with patch("routers.scan.DingTalkClient") as mock_cls:
        mock_dt = AsyncMock()
        mock_dt.send_ambiguous_notification.return_value = 2
        mock_cls.return_value = mock_dt
        r = client.post(f"/scan/{pkg_id}/assign", json={"phone_tail": "1234"})

    assert r.json()["status"] == "ambiguous_notified"
    assert r.json()["count"] == 2
    mock_dt.send_ambiguous_notification.assert_called_once()
    # 包裹仍为待认领，等员工自行认领
    assert session.get(Package, pkg_id).status == PackageStatus.unclaimed


def test_assign_no_match(client, session):
    pkg_id = _scan(client).json()["pkg_id"]
    r = client.post(f"/scan/{pkg_id}/assign", json={"phone_tail": "9999"})
    assert r.json()["status"] == "unmatched"
    assert session.get(Package, pkg_id).status == PackageStatus.unclaimed
