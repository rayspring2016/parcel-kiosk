import pytest
from unittest.mock import patch
from datetime import date
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine, Session
from services.code_gen import generate_code, next_seq
from models import Package


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


def test_code_format():
    with patch("services.code_gen.date") as mock_date:
        mock_date.today.return_value = date(2026, 6, 6)
        code = generate_code(seq=1)
    assert code == "0606-001"


def test_code_seq_padding():
    with patch("services.code_gen.date") as mock_date:
        mock_date.today.return_value = date(2026, 6, 6)
        code = generate_code(seq=42)
    assert code == "0606-042"


def test_code_seq_large():
    with patch("services.code_gen.date") as mock_date:
        mock_date.today.return_value = date(2026, 6, 6)
        code = generate_code(seq=999)
    assert code == "0606-999"


def test_next_seq_empty_day(session):
    """今日无包裹时 COALESCE(MAX, 0)+1 应返回 1，而非 NULL+1=NULL"""
    assert next_seq(session) == 1


def test_next_seq_increments(session):
    """已有 daily_seq=2 时，应返回 3"""
    session.add(Package(code="0606-001", courier="顺丰", daily_seq=1))
    session.add(Package(code="0606-002", courier="京东", daily_seq=2))
    session.commit()
    assert next_seq(session) == 3
