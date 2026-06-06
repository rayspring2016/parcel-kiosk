from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine, Session
from models import Package, PackageStatus


def make_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_create_package():
    s = make_session()
    pkg = Package(slot=1, code="1", courier="顺丰", employee_id="user123")
    s.add(pkg); s.commit(); s.refresh(pkg)
    assert pkg.id is not None
    assert pkg.status == PackageStatus.pending
    assert pkg.slot == 1
    s.close()


def test_package_default_status():
    s = make_session()
    pkg = Package(slot=2, code="2", courier="京东")
    s.add(pkg); s.commit(); s.refresh(pkg)
    assert pkg.status == PackageStatus.pending
    assert pkg.employee_id is None
    s.close()
