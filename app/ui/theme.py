"""色・フォント・暗色スタイルシート。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase

ASSETS = Path(__file__).resolve().parents[2] / "assets"

COLORS = {
    "cyan": "#38E8FF",
    "amber": "#FFB020",
    "red": "#FF3B4E",
    "dim": "#5B7480",
    "bg": "#0C1218",
    "bg2": "#141D25",
    "line": "#23404C",
    "text": "#D6E6EC",
}

# タイマーごとに選べる色（名前 → 表示色）
TIMER_COLORS = {
    "cyan": "#38E8FF",
    "green": "#3CFF9A",
    "magenta": "#FF4FD8",
    "amber": "#FFB020",
    "violet": "#A98BFF",
    "white": "#E8F4F8",
}
TIMER_COLOR_LABELS = {
    "cyan": "シアン", "green": "グリーン", "magenta": "マゼンタ",
    "amber": "アンバー", "violet": "バイオレット", "white": "ホワイト",
}

_font_family: str | None = None


def asset(rel: str) -> Path:
    return ASSETS / rel


def load_fonts() -> str:
    """DSEG7 を登録してファミリー名を返す（2回目以降は登録済みの名前）。"""
    global _font_family
    if _font_family is None:
        fid = QFontDatabase.addApplicationFont(str(asset("fonts/DSEG7Classic-Bold.ttf")))
        QFontDatabase.addApplicationFont(str(asset("fonts/DSEG7Classic-Regular.ttf")))
        families = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
        _font_family = families[0] if families else "Consolas"
    return _font_family


def timer_color(name: str) -> str:
    return TIMER_COLORS.get(name, COLORS["cyan"])


def stylesheet() -> str:
    c = COLORS
    return f"""
    QDialog, QMenu {{
        background: {c["bg"]}; color: {c["text"]};
        border: 1px solid {c["line"]};
    }}
    QWidget {{ color: {c["text"]}; font-family: "Segoe UI", "Yu Gothic UI"; font-size: 10pt; }}
    QLabel#caption {{ color: {c["dim"]}; font-size: 9pt; }}
    QLabel#error {{ color: {c["red"]}; }}
    QLineEdit, QSpinBox, QComboBox, QKeySequenceEdit, QPlainTextEdit, QListWidget {{
        background: {c["bg2"]}; border: 1px solid {c["line"]}; border-radius: 4px;
        padding: 4px 6px; selection-background-color: {c["cyan"]}; selection-color: {c["bg"]};
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QKeySequenceEdit:focus {{
        border-color: {c["cyan"]};
    }}
    QComboBox QAbstractItemView {{ background: {c["bg2"]}; border: 1px solid {c["line"]}; }}
    QPushButton, QToolButton {{
        background: {c["bg2"]}; border: 1px solid {c["line"]}; border-radius: 4px;
        padding: 5px 12px; color: {c["text"]};
    }}
    QPushButton:hover, QToolButton:hover {{ border-color: {c["cyan"]}; color: {c["cyan"]}; }}
    QPushButton:pressed, QToolButton:pressed {{ background: {c["line"]}; }}
    QPushButton:disabled {{ color: {c["dim"]}; border-color: {c["bg2"]}; }}
    QPushButton#primary {{ border-color: {c["cyan"]}; color: {c["cyan"]}; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 14px; height: 14px; border: 1px solid {c["line"]}; background: {c["bg2"]};
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background: {c["cyan"]}; border-color: {c["cyan"]};
    }}
    QRadioButton::indicator {{ border-radius: 7px; }}
    QSlider::groove:horizontal {{ height: 4px; background: {c["line"]}; border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: {c["cyan"]}; border-radius: 2px; }}
    QSlider::handle:horizontal {{
        width: 14px; margin: -6px 0; border-radius: 7px; background: {c["text"]};
    }}
    QMenu::item {{ padding: 5px 22px; }}
    QMenu::item:selected {{ background: {c["line"]}; color: {c["cyan"]}; }}
    QMenu::separator {{ height: 1px; background: {c["line"]}; margin: 4px 8px; }}
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ width: 6px; background: transparent; }}
    QScrollBar::handle:vertical {{ background: {c["line"]}; border-radius: 3px; min-height: 24px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QToolTip {{ background: {c["bg2"]}; color: {c["text"]}; border: 1px solid {c["line"]}; }}
    """
