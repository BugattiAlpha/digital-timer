"""ウィンドウ位置の補正（モニタを外したときなどに画面内へ戻す）。"""
from __future__ import annotations

Rect = tuple[int, int, int, int]  # x, y, w, h


def _overlap(a: Rect, b: Rect) -> int:
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return max(0, w) * max(0, h)


def _center_dist(a: Rect, b: Rect) -> float:
    ax, ay = a[0] + a[2] / 2, a[1] + a[3] / 2
    bx, by = b[0] + b[2] / 2, b[1] + b[3] / 2
    return (ax - bx) ** 2 + (ay - by) ** 2


def clamp_rect(rect: Rect, screens: list[Rect]) -> Rect:
    """rect がいちばん重なっている（無ければ最も近い）画面の内側に収める。"""
    if not screens:
        return rect
    screen = max(screens, key=lambda s: (_overlap(rect, s), -_center_dist(rect, s)))
    sx, sy, sw, sh = screen
    x, y, w, h = rect
    w, h = min(w, sw), min(h, sh)
    x = min(max(x, sx), sx + sw - w)
    y = min(max(y, sy), sy + sh - h)
    return (x, y, w, h)
