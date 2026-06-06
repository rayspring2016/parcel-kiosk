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
    session.add(Package(shelf=1, layer=2, seq=5, code="1-2-0005", courier="圆通",
                        status=PackageStatus.unclaimed))
    session.add(Package(shelf=1, layer=1, seq=6, code="1-1-0006", courier="顺丰", employee_id="u1"))
    session.commit()
    resp = client.get("/unclaimed")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["code"] == "1-2-0005"


def test_claim_package(client, session):
    pkg = Package(shelf=1, layer=2, seq=5, code="1-2-0005", courier="京东",
                  status=PackageStatus.unclaimed)
    session.add(pkg); session.commit(); session.refresh(pkg)
    resp = client.post(f"/unclaimed/{pkg.id}/claim", json={"employee_id": "user_xyz"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["employee_id"] == "user_xyz"
    assert data["code"] == "1-2-0005"


def test_claim_not_found(client):
    resp = client.post("/unclaimed/9999/claim", json={"employee_id": "user_xyz"})
    assert resp.status_code == 404


def test_claim_wrong_status(client, session):
    pkg = Package(shelf=2, layer=1, seq=8, code="2-1-0008", courier="顺丰",
                  status=PackageStatus.pending, employee_id="user_abc")
    session.add(pkg); session.commit(); session.refresh(pkg)
    resp = client.post(f"/unclaimed/{pkg.id}/claim", json={"employee_id": "user_xyz"})
    assert resp.status_code == 404   # pending 状态不能认领
