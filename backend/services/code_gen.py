import threading
from sqlmodel import Session, select, func
from models import Package, PackageStatus

_slot_lock = threading.Lock()   # 单进程下防止并发分配同一位置


def assign_location(
    session: Session,
    max_shelves: int,
    max_layers: int,
    courier: str = "",
    courier_layer_map: dict[str, tuple[int, int]] | None = None,
) -> tuple[int, int, int]:
    """
    返回 (shelf, layer, seq)。

    分配策略：
    1. 若 courier_layer_map 中有该快递公司 → 固定分配到对应货架层
    2. 否则 → 负载均衡（找在库最少的区域）

    seq：全局递增序号，4 位显示，永不重置，避免已删记录导致重号。
    """
    with _slot_lock:
        # ── 确定货架层 ──────────────────────────────────────────
        if courier_layer_map and courier in courier_layer_map:
            shelf, layer = courier_layer_map[courier]
        else:
            # 负载均衡：找在库最少的区域（未知快递公司或未配置时使用）
            rows = session.exec(
                select(Package.shelf, Package.layer, func.count())
                .where(Package.status.in_([PackageStatus.pending, PackageStatus.unclaimed]))
                .group_by(Package.shelf, Package.layer)
            ).all()
            active: dict[tuple[int, int], int] = {(s, l): c for s, l, c in rows}

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

        # ── 全局递增序号 ─────────────────────────────────────────
        max_seq = session.exec(select(func.max(Package.seq))).one()
        seq = (max_seq or 0) + 1

        return shelf, layer, seq
