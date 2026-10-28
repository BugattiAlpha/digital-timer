"""生成画像のパネルを9スライスで描く（四隅は固定、辺と中央だけ伸縮）。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, QRectF, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget


def nine_slice_rects(src: QSize, dst: QRect, margins: tuple[int, int, int, int],
                     scale: float = 1.0) -> list[tuple[QRect, QRect]]:
    """(描画先, 元画像) の矩形を左上→右下の順に9組返す。

    margins は元画像のピクセルで (左, 上, 右, 下)。描画先の縁幅は margins*scale。
    描画先が小さすぎるときは縁が重ならないよう縮める。
    """
    l, t, r, b = margins
    dl, dt, dr, db = (round(v * scale) for v in margins)
    if dl + dr > dst.width():
        f = dst.width() / (dl + dr)
        dl, dr = int(dl * f), int(dr * f)
    if dt + db > dst.height():
        f = dst.height() / (dt + db)
        dt, db = int(dt * f), int(db * f)
    x, y, w, h = dst.x(), dst.y(), dst.width(), dst.height()
    dxs = [x, x + dl, x + w - dr, x + w]
    dys = [y, y + dt, y + h - db, y + h]
    sxs = [0, l, src.width() - r, src.width()]
    sys_ = [0, t, src.height() - b, src.height()]
    pairs = []
    for row in range(3):
        for col in range(3):
            d = QRect(dxs[col], dys[row], dxs[col + 1] - dxs[col], dys[row + 1] - dys[row])
            s = QRect(sxs[col], sys_[row], sxs[col + 1] - sxs[col], sys_[row + 1] - sys_[row])
            pairs.append((d, s))
    return pairs


class PanelWidget(QWidget):
    """背景にパネル画像を敷くだけのウィジェット。子ウィジェットはこの上に置く。"""

    def __init__(self, image: Path, margins: tuple[int, int, int, int], scale: float,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._pixmap = QPixmap(str(image))
        self._margins = margins
        self._scale = scale
        self.outline: QColor | None = None

    def set_outline(self, color: QColor | None) -> None:
        """お知らせの点滅用に、縁に色の線を重ねる（None で消す）。"""
        if color != self.outline:
            self.outline = QColor(color) if color is not None else None
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for d, s in nine_slice_rects(self._pixmap.size(), self.rect(), self._margins, self._scale):
            if d.width() > 0 and d.height() > 0 and s.width() > 0 and s.height() > 0:
                p.drawPixmap(d, self._pixmap, s)
        if self.outline is not None:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(QPen(self.outline, 3))
            p.setBrush(QColor(0, 0, 0, 0))
            inset = 8 * self._scale / 0.3
            p.drawRoundedRect(QRectF(self.rect()).adjusted(inset, inset, -inset, -inset), 10, 10)
        p.end()
