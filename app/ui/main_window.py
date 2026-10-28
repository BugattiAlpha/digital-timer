"""通常表示: パネルの上にタイトルバーとタイマーカードの一覧。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QScrollArea, QSizeGrip, QToolButton,
                               QVBoxLayout, QWidget)

from . import theme
from .floating import FloatingWindow
from .panel import PanelWidget
from .timer_card import TimerCard

if TYPE_CHECKING:
    from ..controller import Controller

# パネル画像（1600px 幅）の縁の幅と、画面上での縮尺
PANEL_MARGINS = (200, 130, 200, 130)
PANEL_SCALE = 0.24


class _TitleBar(QWidget):
    """ドラッグでウィンドウを動かす帯。"""

    def __init__(self, window: FloatingWindow):
        super().__init__()
        self._window = window

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._window.start_drag()


class MainWindow(FloatingWindow):
    def __init__(self, controller: "Controller"):
        super().__init__()
        self.c = controller
        self.setWindowTitle("Digital Timer")
        self.setMinimumSize(380, 260)
        self._cards: dict[str, TimerCard] = {}

        panel = PanelWidget(theme.asset("images/panel.png"), PANEL_MARGINS, PANEL_SCALE)
        self.setCentralWidget(panel)

        bar = _TitleBar(self)
        title = QLabel("DIGITAL TIMER")
        title.setStyleSheet(f"color: {theme.COLORS['cyan']}; font-size: 9pt; font-weight: 600;"
                            " letter-spacing: 3px;")
        bar_lay = QHBoxLayout(bar)
        bar_lay.setContentsMargins(0, 0, 0, 0)
        bar_lay.setSpacing(2)
        bar_lay.addWidget(title)
        bar_lay.addStretch(1)
        for text, tip, slot in (("＋", "タイマーを追加", lambda: controller.edit_timer_dialog()),
                                ("◱", "ミニ表示 (Ctrl+Alt+M)", controller.toggle_mini),
                                ("⚙", "設定", controller.open_settings),
                                ("―", "トレイにしまう", controller.toggle_visible)):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.setAutoRaise(True)
            b.setStyleSheet("QToolButton { border: none; font-size: 12pt; padding: 0 6px; }")
            b.clicked.connect(slot)
            bar_lay.addWidget(b)

        self._list = QWidget()
        self._list_lay = QVBoxLayout(self._list)
        self._list_lay.setContentsMargins(0, 0, 4, 0)
        self._list_lay.setSpacing(8)
        self._empty = QLabel("右上の ＋ からタイマーを追加してください")
        self._empty.setObjectName("caption")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self._list)

        grip_row = QHBoxLayout()
        grip_row.addStretch(1)
        grip_row.addWidget(QSizeGrip(self))

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(36, 22, 36, 14)
        lay.setSpacing(6)
        lay.addWidget(bar)
        lay.addWidget(scroll, 1)
        lay.addLayout(grip_row)

    @staticmethod
    def default_rect() -> QRect:
        s = QGuiApplication.primaryScreen().availableGeometry()
        return QRect(s.right() - 460, s.top() + 40, 440, 540)

    def card(self, timer_id: str) -> TimerCard | None:
        return self._cards.get(timer_id)

    def rebuild(self) -> None:
        for card in self._cards.values():
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()
        while self._list_lay.count():
            self._list_lay.takeAt(0)
        for r in self.c.runtimes:
            card = TimerCard(self.c, r.spec.id)
            self._cards[r.spec.id] = card
            self._list_lay.addWidget(card)
        self._empty.setVisible(not self.c.runtimes)
        self._list_lay.addWidget(self._empty)
        self._list_lay.addStretch(1)

    def closeEvent(self, event):
        # × はトレイにしまうだけ（終了はトレイメニューから）
        event.ignore()
        self.c.toggle_visible()
