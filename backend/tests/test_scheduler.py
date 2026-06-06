import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool
from datetime import datetime, timedelta
from models import Package, PackageStatus


@pytest.fixture
def mem_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_session_mock(real_session):
    """返回一个不关闭 real_session 的 Session mock"""
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=real_session)
    ctx.__exit__ = MagicMock(return_value=None)
    return MagicMock(return_value=ctx)


@pytest.mark.asyncio
async def test_send_reminders_calls_dingtalk(mem_session):
    old_pkg = Package(
        code="0606-001", courier="顺丰", employee_id="user123",
        arrived_at=datetime.now() - timedelta(hours=50)
    )
    mem_session.add(old_pkg)
    mem_session.commit()

    with patch("scheduler.DingTalkClient") as mock_cls, \
         patch("scheduler.Session", _make_session_mock(mem_session)):
        mock_dt = AsyncMock()
        mock_dt.send_reminder = AsyncMock(return_value=True)
        mock_cls.return_value = mock_dt
        from scheduler import send_reminders
        await send_reminders()
    mock_dt.send_reminder.assert_called_once()


@pytest.mark.asyncio
async def test_expire_old_packages(mem_session):
    old_pkg = Package(
        code="0606-002", courier="京东",
        arrived_at=datetime.now() - timedelta(days=8)
    )
    mem_session.add(old_pkg)
    mem_session.commit()

    with patch("scheduler.Session", _make_session_mock(mem_session)):
        from scheduler import expire_old_packages
        await expire_old_packages()

    # session still open — verify status changed
    mem_session.expire(old_pkg)
    mem_session.refresh(old_pkg)
    assert old_pkg.status == PackageStatus.expired


@pytest.mark.asyncio
async def test_pending_not_expired(mem_session):
    recent_pkg = Package(
        code="0606-003", courier="圆通",
        arrived_at=datetime.now() - timedelta(days=3)
    )
    mem_session.add(recent_pkg)
    mem_session.commit()

    with patch("scheduler.Session", _make_session_mock(mem_session)):
        from scheduler import expire_old_packages
        await expire_old_packages()

    mem_session.expire(recent_pkg)
    mem_session.refresh(recent_pkg)
    assert recent_pkg.status == PackageStatus.pending
