from sqlmodel import SQLModel, create_engine, Session, text
from config import DB_PATH

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},  # APScheduler 与 FastAPI 共享同一 SQLite 文件
)


def init_db():
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))   # 允许读写并发，APScheduler 写时 FastAPI 仍可读
        conn.execute(text("PRAGMA synchronous=NORMAL"))
        conn.commit()


def get_session():
    with Session(engine) as session:
        yield session
