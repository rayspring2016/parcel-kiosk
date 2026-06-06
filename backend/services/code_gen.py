import threading
from sqlmodel import Session, select, func
from models import Package, PackageStatus

_slot_lock = threading.Lock()   # 单进程下防止并发分配同一位置


def assign_location(session: Session, max_shelves: int, max_layers: int) -> tuple[int, int, int]:
    """
    返回 (shelf, layer, seq)。
    - shelf/layer：当前在库包裹最少的区域（负载均衡），平局则按编号顺序
    - seq：全局递增序号，4 位显示，永不重置

    设计要点：
    - 不限制每层容量，允许同一层放多个包裹
    - seq 用 MAX+1 而非 COUNT+1，避免已删记录导致重号
    """
    with _slot_lock:
        # 统计各区域在库数量
        rows = session.exec(
            select(Package.shelf, Package.layer, func.count())
            .where(Package.status.in_([PackageStatus.pending, PackageStatus.unclaimed]))
            .group_by(Package.shelf, Package.layer)
        ).all()
        active: dict[tuple[int, int], int] = {(s, l): c for s, l, c in rows}

        # 找在库最少的区域（按货架、层顺序优先）
        best: tuple[int, int] | None = None
        best_count = float("inf")
        for s in range(1, max_shelves + 1):
            for l in range(1, max_layers + 1):
                count = active.get((s, l), 0)
                if count < best_count:
                    best_count = count
                    best = (s, l)

        assert best is not None
        shelf, layer = best

        # 全局递增序号
        max_seq = session.exec(select(func.max(Package.seq))).one()
        seq = (max_seq or 0) + 1

        return shelf, layer, seq
