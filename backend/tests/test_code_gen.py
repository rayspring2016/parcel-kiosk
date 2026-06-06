from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine, Session
from services.code_gen import assign_slot
from models import Package, PackageStatus
import pytest


def make_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_assign_slot_empty():
    """无包裹时应分配到格子 1"""
    s = make_session()
    assert assign_slot(s, max_slots=30) == 1
    s.close()


def test_assign_slot_skips_occupied():
    """格子 1、2 已占用，应分配到格子 3"""
    s = make_session()
    s.add(Package(slot=1, code="1", courier="顺丰"))
    s.add(Package(slot=2, code="2", courier="京东"))
    s.commit()
    assert assign_slot(s, max_slots=30) == 3
    s.close()


def test_assign_slot_reuses_after_pickup():
    """格子 1 取走后（picked_up），可以重新分配给新包裹"""
    s = make_session()
    from datetime import datetime
    s.add(Package(slot=1, code="1", courier="顺丰",
                  status=PackageStatus.picked_up,
                  picked_at=datetime.now()))
    s.add(Package(slot=2, code="2", courier="京东"))
    s.commit()
    assert assign_slot(s, max_slots=30) == 1   # 格子 1 已空，应优先复用
    s.close()


def test_assign_slot_full_raises():
    """所有格子占满时应抛出 RuntimeError"""
    s = make_session()
    for i in range(1, 4):
        s.add(Package(slot=i, code=str(i), courier="顺丰"))
    s.commit()
    with pytest.raises(RuntimeError, match="格子"):
        assign_slot(s, max_slots=3)
    s.close()


def test_assign_slot_unclaimed_counts_as_occupied():
    """待认领包裹仍占用格子，不能被新包裹覆盖"""
    s = make_session()
    s.add(Package(slot=1, code="待认领-01", courier="圆通",
                  status=PackageStatus.unclaimed))
    s.commit()
    assert assign_slot(s, max_slots=30) == 2   # 格子 1 被待认领占用，分配格子 2
    s.close()
