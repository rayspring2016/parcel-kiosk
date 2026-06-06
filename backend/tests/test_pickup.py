import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine, Session
from datetime import datetime
from main import app
from database import get_session
from models import Package, PackageStatus


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


def test_pickup_success(client, session):
    pkg = Package(shelf=1, layer=2, seq=7, code="1-2-0007", courier="顺丰", employee_id="user123")
    session.add(pkg); session.commit(); session.refresh(pkg)
    resp = client.post(f"/pickup/{pkg.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "picked_up"
    assert data["code"] == "1-2-0007"


def test_pickup_not_found(client):
    resp = client.post("/pickup/9999")
    assert resp.status_code == 404


def test_pickup_already_done(client, session):
    pkg = Package(
        shelf=1, layer=2, seq=7, code="1-2-0007", courier="京东", employee_id="user123",
        status=PackageStatus.picked_up, picked_at=datetime.now()
    )
    session.add(pkg); session.commit(); session.refresh(pkg)
    resp = client.post(f"/pickup/{pkg.id}")
    assert resp.status_code == 404   # picked_up 状态拒绝重复取件


def test_my_packages(client, session):
    session.add(Package(shelf=1, layer=1, seq=3, code="1-1-0003", courier="顺丰", employee_id="user123"))
    session.add(Package(shelf=1, layer=2, seq=4, code="1-2-0004", courier="京东", employee_id="user456"))
    session.commit()
    resp = client.get("/my-packages?employee_id=user123")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["code"] == "1-1-0003"
    assert data[0]["shelf"] == 1
    assert data[0]["layer"] == 1


def test_get_confirm_page(client, session):
    pkg = Package(shelf=2, layer=3, seq=5, code="2-3-0005", courier="圆通", employee_id="user123")
    session.add(pkg); session.commit(); session.refresh(pkg)
    resp = client.get(f"/pickup/confirm/{pkg.id}")
    assert resp.status_code == 200
    assert "2-3-0005" in resp.text
