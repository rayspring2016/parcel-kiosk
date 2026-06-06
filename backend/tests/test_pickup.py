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
    session.add(Package(slot=7, code="7", courier="顺丰", employee_id="user123"))
    session.commit()
    resp = client.post("/pickup/7")
    assert resp.status_code == 200
    assert resp.json()["status"] == "picked_up"
    assert resp.json()["slot"] == 7


def test_pickup_not_found(client):
    resp = client.post("/pickup/99")
    assert resp.status_code == 404


def test_pickup_already_done(client, session):
    session.add(Package(
        slot=7, code="7", courier="京东", employee_id="user123",
        status=PackageStatus.picked_up, picked_at=datetime.now()
    ))
    session.commit()
    resp = client.post("/pickup/7")
    assert resp.status_code == 404   # picked_up 包裹在查询中不存在


def test_my_packages(client, session):
    session.add(Package(slot=3, code="3", courier="顺丰", employee_id="user123"))
    session.add(Package(slot=4, code="4", courier="京东", employee_id="user456"))
    session.commit()
    resp = client.get("/my-packages?employee_id=user123")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["slot"] == 3


def test_get_confirm_page(client, session):
    pkg = Package(slot=5, code="5", courier="圆通", employee_id="user123")
    session.add(pkg); session.commit(); session.refresh(pkg)
    resp = client.get(f"/pickup/confirm/{pkg.id}")
    assert resp.status_code == 200
    assert "05" in resp.text   # slot 5 formatted as 05
