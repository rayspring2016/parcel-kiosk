import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine, Session
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


def test_list_unclaimed(client, session):
    session.add(Package(slot=5, code="待认领-05", courier="圆通",
                        status=PackageStatus.unclaimed))
    session.add(Package(slot=6, code="6", courier="顺丰", employee_id="u1"))
    session.commit()
    resp = client.get("/unclaimed")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["slot"] == 5


def test_claim_package(client, session):
    session.add(Package(slot=5, code="待认领-05", courier="京东",
                        status=PackageStatus.unclaimed))
    session.commit()
    resp = client.post("/unclaimed/5/claim", json={"employee_id": "user_xyz"})
    assert resp.status_code == 200
    assert resp.json()["employee_id"] == "user_xyz"
    assert resp.json()["slot"] == 5


def test_claim_not_found(client):
    resp = client.post("/unclaimed/99/claim", json={"employee_id": "user_xyz"})
    assert resp.status_code == 404


def test_claim_wrong_status(client, session):
    session.add(Package(slot=8, code="8", courier="顺丰",
                        status=PackageStatus.pending, employee_id="user_abc"))
    session.commit()
    resp = client.post("/unclaimed/8/claim", json={"employee_id": "user_xyz"})
    assert resp.status_code == 404   # pending 包裹不在 unclaimed 查询里
