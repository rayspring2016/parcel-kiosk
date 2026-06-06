from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine, Session
from services.code_gen import assign_location
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


def test_assign_empty():
    """空库时应分配到货架 1、第 1 层，seq=1"""
    s = make_session()
    shelf, layer, seq = assign_location(s, max_shelves=2, max_layers=4)
    assert (shelf, layer, seq) == (1, 1, 1)
    s.close()


def test_assign_balances_load():
    """1-1 已有包裹，新包裹应分配到其他区域（1-2）"""
    s = make_session()
    s.add(Package(shelf=1, layer=1, seq=1, code="1-1-0001", courier="顺丰"))
    s.commit()
    shelf, layer, seq = assign_location(s, max_shelves=2, max_layers=4)
    assert (shelf, layer) == (1, 2)   # 1-1 有 1 个，1-2 为空，优先 1-2
    assert seq == 2
    s.close()


def test_seq_increments_globally():
    """seq 全局递增，即使新包裹放到不同区域"""
    s = make_session()
    s.add(Package(shelf=1, layer=1, seq=5, code="1-1-0005", courier="顺丰"))
    s.commit()
    _, _, seq = assign_location(s, max_shelves=2, max_layers=4)
    assert seq == 6
    s.close()


def test_picked_up_zone_reused():
    """已取走包裹（picked_up）不占区域，空区域应优先"""
    from datetime import datetime
    s = make_session()
    # 1-1 有已取件包裹，不算占用
    s.add(Package(shelf=1, layer=1, seq=1, code="1-1-0001", courier="顺丰",
                  status=PackageStatus.picked_up, picked_at=datetime.now()))
    # 1-2 有在库包裹
    s.add(Package(shelf=1, layer=2, seq=2, code="1-2-0002", courier="京东"))
    s.commit()
    shelf, layer, _ = assign_location(s, max_shelves=2, max_layers=4)
    assert (shelf, layer) == (1, 1)   # 1-1 已取件不占，应优先分配
    s.close()


def test_unclaimed_counts_as_occupied():
    """待认领包裹仍占区域，不被覆盖"""
    s = make_session()
    s.add(Package(shelf=1, layer=1, seq=1, code="1-1-0001", courier="圆通",
                  status=PackageStatus.unclaimed))
    s.commit()
    shelf, layer, _ = assign_location(s, max_shelves=2, max_layers=4)
    assert (shelf, layer) == (1, 2)   # 1-1 被待认领占用，分配 1-2
    s.close()
