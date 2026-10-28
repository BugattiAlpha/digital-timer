"""ミニ表示: チェックしたタイマーを、数字と進捗だけの小さなパネルで縦に並べる。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QAction, QColor, QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QVBoxLayout, QWidget

from ..core.geometry import clamp_rect
from ..core.timers import State
from . import theme
from .digits import DigitDisplay
from .display import Display
from .elided import ElidedLabel
from .floating import FloatingWindow, ProgressLine
from .panel import PanelWidget
from .timer_card import color_of

if TYPE_CHECKING:
    from ..controller import Controller

# 9スライスの固定部分。ガラスの縁の溝と四隅の飾りまでを含め、伸ばしてもガラス面の位置が変わらないようにする
PANEL_MARGINS = (124, 112, 124, 120)
PANEL_SCALE = 0.3
MIN_PANEL_SIZE = (240, 116)
DEFAULT_PANEL_SIZE = (320, 124)


class MiniPanel(PanelWidget):
    """タイマー1つ分のパネル。timer_id が None なら「タイマーがありません」。"""

    def __init__(self, timer_id: str | None):
        super().__init__(theme.asset("images/mini_panel.png"), PANEL_MARGINS, PANEL_SCALE)
        self.timer_id = timer_id
        label_css = f"color: {theme.COLORS['text']}; font-size: 8pt;"
        self.name = ElidedLabel()  # 名前が長いときは名前を省略し、状態（一時停止中など）は全部見せる
        self.name.setStyleSheet(label_css)
        self.status = QLabel()
        self.status.setStyleSheet(label_css)
        head = QHBoxLayout()
        head.setSpacing(10)
        head.addWidget(self.name, 1)
        head.addWidget(self.status)
        self.digits = DigitDisplay()
        self.progress = ProgressLine()
        lay = QVBoxLayout(self)
        # 縁（金属部分と溝）に文字がかからないよう、ガラス面（縁から左右37・上34・下27px）の内側に収める
        lay.setContentsMargins(42, 36, 42, 30)
        lay.setSpacing(2)
        lay.addLayout(head)
        lay.addWidget(self.digits, 1)
        lay.addWidget(self.progress)
        self._name_css = ""

    def refresh(self, name: str, d: Display | None, flashing: bool, phase: bool, focused: bool) -> None:
        self.set_outline(QColor(theme.COLORS["red"]) if flashing and phase else None)
        # 複数並べているとき、ショートカットが効くパネルの名前をタイマー色で示す
        css = f"color: {theme.COLORS['cyan'] if focused else theme.COLORS['text']}; font-size: 8pt;"
        if css != self._name_css:
            self._name_css = css
            self.name.setStyleSheet(css)
        if d is None:
            self.name.setText("タイマーがありません")
            self.status.setText("")
            self.digits.set_text("00:00:00")
            self.digits.set_color(color_of("cyan"))
            self.progress.set_value(0, color_of("cyan"))
            return
        self.name.setText(name)
        self.status.setText(d.status.split(" · ", 1)[-1] if " · " in d.status else "")
        self.digits.set_text(d.text)
        self.digits.set_color(color_of(d.color))
        self.digits.set_flash(flashing)
        if flashing:
            self.digits.flash_phase = phase
            self.digits.update()
        self.progress.set_value(d.progress, color_of(d.color))


class MiniWindow(FloatingWindow):
    def __init__(self, controller: "Controller"):
        super().__init__()
        self.c = controller
        self.setWindowTitle("Digital Timer (mini)")
        body = QWidget()
        self._lay = QVBoxLayout(body)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)
        self.setCentralWidget(body)
        self.panels: list[MiniPanel] = []
        self.set_timers([None])

    # 1つだけ出していた頃と同じ書き方で先頭のパネルを触れるようにする
    @property
    def panel(self) -> MiniPanel:
        return self.panels[0]

    @property
    def name(self) -> ElidedLabel:
        return self.panels[0].name

    @property
    def status(self) -> QLabel:
        return self.panels[0].status

    @property
    def digits(self) -> DigitDisplay:
        return self.panels[0].digits

    @property
    def progress(self) -> ProgressLine:
        return self.panels[0].progress

    @staticmethod
    def default_rect() -> QRect:
        s = QGuiApplication.primaryScreen().availableGeometry()
        w, h = DEFAULT_PANEL_SIZE
        return QRect(s.right() - w - 20, s.top() + 40, w, h)

    def timer_ids(self) -> list[str | None]:
        return [p.timer_id for p in self.panels]

    def set_timers(self, ids: Sequence[str | None]) -> None:
        """並べるタイマーを変える。パネル1枚あたりの高さは保ったまま、窓の高さを枚数に合わせる。"""
        ids = list(ids) or [None]
        if ids == self.timer_ids():
            return
        per_h = max(MIN_PANEL_SIZE[1], self.height() // len(self.panels)) if self.panels else DEFAULT_PANEL_SIZE[1]
        for p in self.panels:
            # 削除は後回しになるので、それまで古いパネルが新しいパネルに重なって描かれないよう先に隠す
            self._lay.removeWidget(p)
            p.hide()
            p.deleteLater()
        self.panels = [MiniPanel(tid) for tid in ids]
        for p in self.panels:
            self._lay.addWidget(p, 1)
        # 枚数が多くて画面に収まらないときは、1枚あたりを低くして画面の高さに収める
        screen = self.screen() or QGuiApplication.primaryScreen()
        area_h = screen.availableGeometry().height()
        n = len(ids)
        min_h = min(MIN_PANEL_SIZE[1], area_h // n)
        per_h = max(min_h, min(per_h, area_h // n))
        self.setMinimumSize(MIN_PANEL_SIZE[0], min_h * n)
        # 下に伸びて画面からはみ出すときは、上にずらして画面内に収める
        screens = [s.availableGeometry() for s in QGuiApplication.screens()]
        x, y, w, h = clamp_rect((self.x(), self.y(), max(self.width(), MIN_PANEL_SIZE[0]), per_h * n),
                                [(s.x(), s.y(), s.width(), s.height()) for s in screens])
        self.setGeometry(x, y, w, h)
        # 隠れている間は Qt がリサイズを知らせないので、保存する大きさを自分で更新させる
        if not self._restoring:
            self.geometry_changed.emit()

    def panel_at(self, pos: QPoint) -> MiniPanel | None:
        """ウィンドウ内の位置にあるパネル。"""
        body = self.centralWidget()
        if body is None:
            return None
        for p in self.panels:
            if p.geometry().contains(body.mapFrom(self, pos)):
                return p
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            p = self.panel_at(event.position().toPoint())
            if p is not None and p.timer_id:
                self.c.focus_mini(p.timer_id)  # クリックしたタイマーにショートカットが効く
                if self.c.alerts.is_active(p.timer_id):
                    self.c.alerts.dismiss(p.timer_id)
            self.start_drag()

    def mouseDoubleClickEvent(self, event):
        self.c.toggle_mini()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        if self.c.runtimes:
            menu.addSection("ミニ表示に出すタイマー")
        shown = set(self.c.settings.mini_timer_ids)  # チェックの表示と切り替えは、チェックした一覧が基準
        for r in self.c.runtimes:
            act = QAction(r.spec.name, menu)
            act.setCheckable(True)
            act.setChecked(r.spec.id in shown)
            act.triggered.connect(lambda on, tid=r.spec.id: self.c.set_mini_shown(tid, on))
            menu.addAction(act)
        if self.c.runtimes:
            menu.addSeparator()
        p = self.panel_at(event.pos())
        target = p.timer_id if p is not None else None
        if target:
            running = self.c.runtime(target).state == State.RUNNING
            menu.addAction("一時停止" if running else "スタート", lambda: self.c.toggle(target))
            menu.addAction("リセット", lambda: self.c.reset(target))
            menu.addSeparator()
        menu.addAction("通常表示に戻る", self.c.toggle_mini)
        menu.exec(event.globalPos())

    def closeEvent(self, event):
        event.ignore()
        self.c.toggle_visible()
