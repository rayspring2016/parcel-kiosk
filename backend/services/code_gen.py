import threading
from datetime import date, datetime
from sqlmodel import Session, select, func
from models import Package

_seq_lock = threading.Lock()  # 单进程部署下防止并发 next_seq 产生相同序号


def generate_code(seq: int) -> str:
    today = date.today()
    return f"{today.strftime('%m%d')}-{seq:03d}"


def next_seq(session: Session) -> int:
    """
    原实现用 COUNT(*)+1 存在竞态：两个并发请求同时读到 count=5，都返回 6。
    改为 SELECT COALESCE(MAX(daily_seq), 0)+1，配合模块级锁确保原子性。
    COALESCE 处理今日第一单时 MAX 返回 NULL 的边界情况。
    """
    with _seq_lock:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        result = session.exec(
            select(func.coalesce(func.max(Package.daily_seq), 0))
            .where(Package.arrived_at >= today_start)
        ).one()
        return result + 1
