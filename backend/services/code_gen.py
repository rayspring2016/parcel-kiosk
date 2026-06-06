import threading
from sqlmodel import Session, select
from models import Package, PackageStatus

_slot_lock = threading.Lock()   # 单进程下防止并发分配同一格子


def assign_slot(session: Session, max_slots: int) -> int:
    """
    返回当前最小空闲格子编号（1 ~ max_slots）。
    "空闲"定义：没有状态为 pending / unclaimed 的包裹占用该格子。
    取走即空、可立刻复用。

    使用 threading.Lock 而非数据库事务锁：
    - 项目为单进程部署（uvicorn --workers 1），Lock 足够防竞态
    - 多进程/多机场景需改为 SELECT FOR UPDATE 或 Redis 分布式锁
    """
    with _slot_lock:
        occupied = set(
            session.exec(
                select(Package.slot).where(
                    Package.status.in_([PackageStatus.pending, PackageStatus.unclaimed])
                )
            ).all()
        )
        for slot in range(1, max_slots + 1):
            if slot not in occupied:
                return slot
        raise RuntimeError(f"所有 {max_slots} 个格子均已占满，请先处理待取包裹")
