import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine, Session
from main import app
from database import get_session
from models import Package, PackageStatus
from datetime import datetime


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
