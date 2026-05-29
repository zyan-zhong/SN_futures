from __future__ import annotations


def apply_slippage(price: float, *, signal: int, is_entry: bool, tick_size: float, slippage_ticks: float) -> float:
    """Apply conservative execution slippage.

    Long entry and short exit pay up; short entry and long exit receive down.
    """

    direction = 1 if int(signal) > 0 else -1
    if not is_entry:
        direction *= -1
    return float(price) + direction * float(slippage_ticks) * float(tick_size)

