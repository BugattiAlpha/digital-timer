"""入りきらない分を「…」で省略する1行ラベル。"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QLabel


class ElidedLabel(QLabel):
    """入りきらない分を「…」で省略する1行ラベル。幅が足りないときは他の部品に幅を譲る。"""

    def shown_text(self) -> str:
        return self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width())

    def minimumSizeHint(self) -> QSize:
        return QSize(0, super().minimumSizeHint().height())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setPen(self.palette().windowText().color())
        p.drawText(self.rect(), int(self.alignment()), self.shown_text())
        p.end()
