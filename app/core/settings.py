"""アプリ全体の設定。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields

DEFAULT_HOTKEYS = {
    "toggle": "Ctrl+Alt+S",
    "reset": "Ctrl+Alt+R",
    "lap": "Ctrl+Alt+L",
    "mini": "Ctrl+Alt+M",
    "clickthrough": "Ctrl+Alt+T",
    "show": "Ctrl+Alt+H",
    "dismiss": "Ctrl+Alt+A",
}

HOTKEY_LABELS = {
    "toggle": "スタート / 一時停止",
    "reset": "リセット",
    "lap": "ラップ",
    "mini": "ミニ表示の切替",
    "clickthrough": "クリック透過の切替",
    "show": "表示 / 非表示",
    "dismiss": "お知らせを止める",
}

MIN_OPACITY = 0.2
MAX_OPACITY = 1.0


@dataclass
class Settings:
    opacity: float = 0.92
    always_on_top: bool = True
    mini_mode: bool = False
    sound_name: str = "chime"
    volume: float = 0.7
    hotkeys: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_HOTKEYS))
    normal_rect: list[int] | None = None
    mini_rect: list[int] | None = None
    mini_timer_id: str | None = None  # ミニ表示でショートカットが効くタイマー（クリックしたもの）
    mini_timer_ids: list[str] = field(default_factory=list)  # ミニ表示に出すタイマー（チェックしたもの）
    selected_timer_id: str | None = None

    def to_dict(self) -> dict:
        # クリック透過は保存しない（起動直後に操作できない状態を避ける）
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Settings":
        known = {f.name for f in fields(cls)}
        s = cls(**{k: v for k, v in d.items() if k in known})
        s.opacity = clamp_opacity(float(s.opacity))
        s.volume = min(1.0, max(0.0, float(s.volume)))
        hotkeys = dict(DEFAULT_HOTKEYS)
        if isinstance(d.get("hotkeys"), dict):
            hotkeys.update({k: str(v) for k, v in d["hotkeys"].items() if k in DEFAULT_HOTKEYS})
        s.hotkeys = hotkeys
        ids = d.get("mini_timer_ids")
        if isinstance(ids, list):
            s.mini_timer_ids = [str(x) for x in ids]
        else:  # 1つだけ出していた頃の保存データ
            s.mini_timer_ids = [s.mini_timer_id] if s.mini_timer_id and ids is None else []
        return s


def clamp_opacity(value: float) -> float:
    return min(MAX_OPACITY, max(MIN_OPACITY, value))
