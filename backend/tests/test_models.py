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
    pkg = Package(shelf=1, layer=2, seq=1, code="1-2-0001", courier="顺丰", employee_id="user123")
    s.add(pkg); s.commit(); s.refresh(pkg)
    assert pkg.id is not None
    assert pkg.status == PackageStatus.pending
    assert pkg.shelf == 1
    assert pkg.layer == 2
    assert pkg.seq == 1
    assert pkg.code == "1-2-0001"
    s.close()


def test_package_default_status():
    s = make_session()
    pkg = Package(shelf=2, layer=3, seq=2, code="2-3-0002", courier="京东")
    s.add(pkg); s.commit(); s.refresh(pkg)
    assert pkg.status == PackageStatus.pending
    assert pkg.employee_id is None
    s.close()
