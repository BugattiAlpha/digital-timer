"""通常表示に並べるタイマー1つ分のカード。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QPlainTextEdit,
                               QPushButton, QToolButton, QVBoxLayout, QWidget)

from ..core.fmt import format_clock
from ..core.timers import Kind, State
from . import theme
from .digits import DigitDisplay
from .display import Display
from .elided import ElidedLabel
from .floating import ProgressLine

if TYPE_CHECKING:
    from ..controller import Controller


def color_of(name: str) -> QColor:
    """タイマー色の名前、または警告色 "amber" / 超過色 "red" を色にする。"""
    if name == "red":
        return QColor(theme.COLORS["red"])
    return QColor(theme.timer_color(name))


class TimerCard(QFrame):
    def __init__(self, controller: "Controller", timer_id: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.c = controller
        self.timer_id = timer_id
        self._selected = False
        self._flash_on = False
        self._accent = QColor(theme.COLORS["cyan"])
        r = controller.runtime(timer_id)
        kind = r.spec.kind

        self.dot = QLabel("●")
        self.name = ElidedLabel()  # 長い名前は省略して、編集・削除ボタンを押せるように残す
        self.name.setStyleSheet("font-weight: 600;")
        self.status = QLabel()
        self.status.setObjectName("caption")
        self.mini_check = QCheckBox("ミニ")
        self.mini_check.setToolTip("ミニ表示に出す")
        self.mini_check.toggled.connect(lambda on: controller.set_mini_shown(timer_id, on))
        edit = self._tool("✎", "編集", lambda: controller.edit_timer_dialog(timer_id))
        delete = self._tool("✕", "削除", self._confirm_delete)
        head = QHBoxLayout()
        head.setSpacing(6)
        head.addWidget(self.dot)
        head.addWidget(self.name, 1)
        head.addWidget(self.status)
        head.addWidget(edit)
        head.addWidget(delete)

        self.digits = DigitDisplay()
        self.digits.setFixedHeight(56)
        self.progress = ProgressLine()

        self.start_btn = QPushButton()
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(lambda: controller.toggle(timer_id))
        reset = QPushButton("↺ リセット")
        reset.clicked.connect(lambda: controller.reset(timer_id))
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        buttons.addWidget(self.start_btn)
        buttons.addWidget(reset)
        self.laps_btn: QPushButton | None = None
        self.laps: QPlainTextEdit | None = None
        self.copy_btn: QPushButton | None = None
        if kind == Kind.STOPWATCH:
            lap = QPushButton("ラップ")
            lap.clicked.connect(lambda: controller.lap(timer_id))
            laps_btn = QPushButton()
            laps_btn.setCheckable(True)
            laps_btn.setToolTip("ラップ一覧を開く/閉じる（数字はラップの数）")
            laps_btn.toggled.connect(self._toggle_laps)
            self.laps_btn = laps_btn
            buttons.addWidget(lap)
            buttons.addWidget(laps_btn)
        elif kind == Kind.POMODORO:
            skip = QPushButton("スキップ ⏭")
            skip.setToolTip("今の作業/休憩を飛ばして次へ")
            skip.clicked.connect(lambda: controller.skip(timer_id))
            buttons.addWidget(skip)
        buttons.addStretch(1)
        buttons.addWidget(self.mini_check)  # 見出しに置くと名前の幅が足りなくなるので、ボタンの右端に置く

        # カードのボタンは余白を詰める（ストップウォッチの「❚❚ 一時停止」とラップ・「ミニ」が1行に収まるように）
        self.setStyleSheet("QPushButton { padding: 5px 8px; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 10)
        lay.setSpacing(4)
        lay.addLayout(head)
        lay.addWidget(self.digits)
        lay.addWidget(self.progress)
        lay.addLayout(buttons)
        if kind == Kind.STOPWATCH:
            self.laps = QPlainTextEdit()
            self.laps.setReadOnly(True)
            self.laps.setFixedHeight(90)
            self.laps.setStyleSheet("font-family: Consolas; font-size: 9pt;")
            self.copy_btn = QPushButton("ラップをコピー")
            self.copy_btn.clicked.connect(self._copy_laps)
            self.laps.hide()
            self.copy_btn.hide()
            lay.addWidget(self.laps)
            lay.addWidget(self.copy_btn, 0, Qt.AlignmentFlag.AlignRight)

    def _tool(self, text: str, tip: str, slot) -> QToolButton:
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.setAutoRaise(True)
        b.setStyleSheet("QToolButton { border: none; padding: 0 4px; }")
        b.clicked.connect(slot)
        return b

    def _confirm_delete(self) -> None:
        name = self.c.runtime(self.timer_id).spec.name
        if self.c.confirm("削除", f"「{name}」を削除しますか？"):
            self.c.remove_timer(self.timer_id)

    def _toggle_laps(self, on: bool) -> None:
        if self.laps and self.copy_btn:
            self.laps.setVisible(on)
            self.copy_btn.setVisible(on)

    def _laps_text(self) -> str:
        laps = self.c.runtime(self.timer_id).laps
        lines, prev = [], 0.0
        for i, t in enumerate(laps, 1):
            lines.append(f"#{i:<3} {format_clock(t, centis=True)}  (+{format_clock(t - prev, centis=True)})")
            prev = t
        return "\n".join(lines)

    def _copy_laps(self) -> None:
        QGuiApplication.clipboard().setText(self._laps_text())

    def refresh(self, d: Display, selected: bool, flashing: bool, phase: bool) -> None:
        r = self.c.runtime(self.timer_id)
        accent = color_of(r.spec.color)
        self.name.setText(r.spec.name)
        self.dot.setStyleSheet(f"color: {accent.name()};")
        self.status.setText(d.status)
        checked = self.timer_id in self.c.settings.mini_timer_ids
        if self.mini_check.isChecked() != checked:
            self.mini_check.blockSignals(True)
            self.mini_check.setChecked(checked)
            self.mini_check.blockSignals(False)
        self.digits.set_text(d.text)
        self.digits.set_color(color_of(d.color))
        self.digits.set_flash(flashing)
        if flashing:
            self.digits.flash_phase = phase
            self.digits.update()
        self.progress.set_value(d.progress, color_of(d.color))
        self.start_btn.setText({State.RUNNING: "❚❚ 一時停止", State.PAUSED: "▶ 再開"}
                               .get(r.state, "▶ スタート"))
        if self.laps_btn is not None and self.laps is not None:
            self.laps_btn.setText(f"☰ {len(r.laps)}")  # 狭いカードでも「ミニ」と並ぶよう短く（ツールチップで説明）
            text = self._laps_text()
            if self.laps.toPlainText() != text:
                self.laps.setPlainText(text)
                self.laps.verticalScrollBar().setValue(self.laps.verticalScrollBar().maximum())
        flash_on = flashing and phase
        if (selected, flash_on, accent) != (self._selected, self._flash_on, self._accent):
            self._selected, self._flash_on, self._accent = selected, flash_on, accent
            self.update()

    def mousePressEvent(self, event):
        self.c.select(self.timer_id)
        if self.c.alerts.is_active(self.timer_id):
            self.c.alerts.dismiss(self.timer_id)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setBrush(QColor(6, 12, 18, 170))
        if self._flash_on:
            border = QColor(theme.COLORS["red"])
            width = 2.0
        elif self._selected:
            border = QColor(self._accent)
            border.setAlpha(170)
            width = 1.4
        else:
            border = QColor(theme.COLORS["line"])
            width = 1.0
        p.setPen(QPen(border, width))
        p.drawRoundedRect(rect, 6, 6)
        p.end()
