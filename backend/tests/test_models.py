import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine, Session
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
