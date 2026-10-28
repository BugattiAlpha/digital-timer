"""通常表示・ミニ表示に共通の、枠なし・半透明・最前面のウィンドウ。"""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QGuiApplication, QPainter, QColor
from PySide6.QtWidgets import QMainWindow, QWidget

from ..core.geometry import clamp_rect


class FloatingWindow(QMainWindow):
    geometry_changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # お知らせなどで表示し直してもフォーカスを奪わない
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._restoring = False

    def apply_flags(self, on_top: bool, click_through: bool) -> None:
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on_top)
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, click_through)
        if visible:
            self.show()

    def restore_geometry(self, rect: list[int] | None, default: QRect) -> None:
        r = QRect(*rect) if rect and len(rect) == 4 else default
        screens = [s.availableGeometry() for s in QGuiApplication.screens()]
        x, y, w, h = clamp_rect((r.x(), r.y(), r.width(), r.height()),
                                [(s.x(), s.y(), s.width(), s.height()) for s in screens])
        self._restoring = True
        self.setGeometry(x, y, max(w, self.minimumWidth()), max(h, self.minimumHeight()))
        self._restoring = False

    def rect_list(self) -> list[int]:
        g = self.geometry()
        return [g.x(), g.y(), g.width(), g.height()]

    def start_drag(self) -> None:
        handle = self.windowHandle()
        if handle is not None:
            handle.startSystemMove()

    def moveEvent(self, event):
        super().moveEvent(event)
        if not self._restoring:
            self.geometry_changed.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._restoring:
            self.geometry_changed.emit()


class ProgressLine(QWidget):
    """細い進捗バー（タイマー色）。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(3)
        self._value = 0.0
        self._color = QColor("#38E8FF")

    def set_value(self, value: float, color: QColor) -> None:
        if value != self._value or color != self._color:
            self._value, self._color = value, QColor(color)
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        track = QColor(self._color)
        track.setAlpha(40)
        p.fillRect(self.rect(), track)
        w = int(self.width() * max(0.0, min(1.0, self._value)))
        if w:
            p.fillRect(0, 0, w, self.height(), self._color)
        p.end()
