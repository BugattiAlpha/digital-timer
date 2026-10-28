"""光る7セグ数字の表示。消灯セグメント（薄い 8）＋グロー＋本体の3層で描く。"""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter
from PySide6.QtWidgets import QWidget

from . import theme


def ghost_text(text: str) -> str:
    """同じ幅の「全点灯」文字列（消灯セグメントの下絵）。"""
    return "".join(ch if ch in ":." else "8" for ch in text)


class DigitDisplay(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._text = "00:00:00"
        self._color = QColor(theme.COLORS["cyan"])
        self._family = theme.load_fonts()
        self._flash = False
        self.flash_phase = True  # 点滅中の点灯/消灯（AlertManager が切り替える）
        self._cache: tuple | None = None
        self._cache_img: QImage | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(80, 24)

    def sizeHint(self) -> QSize:
        return QSize(320, 80)

    def set_text(self, text: str) -> None:
        if text != self._text:
            self._text = text
            self.update()

    def set_color(self, color: QColor) -> None:
        if color != self._color:
            self._color = QColor(color)
            self.update()

    def set_flash(self, on: bool) -> None:
        if on == self._flash:
            return
        self._flash = on
        self.flash_phase = True
        self.update()

    def toggle_flash_phase(self) -> None:
        self.flash_phase = not self.flash_phase
        self.update()

    def _fit_font(self) -> QFont:
        font = QFont(self._family)
        font.setPointSizeF(100)
        m = QFontMetricsF(font)
        ghost = ghost_text(self._text)
        w = m.horizontalAdvance(ghost) or 1
        h = m.height() or 1
        size = 100 * min(self.width() * 0.94 / w, self.height() * 0.86 / h)
        font.setPointSizeF(max(4.0, size))
        return font

    def _render(self) -> QImage:
        key = (self._text, self._color.rgba(), self.width(), self.height(), self.devicePixelRatioF())
        if self._cache == key and self._cache_img is not None:
            return self._cache_img
        dpr = self.devicePixelRatioF()
        img = QImage(int(self.width() * dpr), int(self.height() * dpr),
                     QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(Qt.GlobalColor.transparent)
        font = self._fit_font()
        rect = QRectF(0, 0, self.width(), self.height())
        align = Qt.AlignmentFlag.AlignCenter

        # 本体（グロー用に別画像にも描く）
        body = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
        body.setDevicePixelRatio(dpr)
        body.fill(Qt.GlobalColor.transparent)
        bp = QPainter(body)
        bp.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        bp.setFont(font)
        bp.setPen(self._color)
        bp.drawText(rect, align, self._text)
        bp.end()

        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setFont(font)
        ghost = QColor(self._color)
        ghost.setAlpha(28)
        p.setPen(ghost)
        p.drawText(rect, align, ghost_text(self._text))
        # 縮小→拡大でぼかした本体を重ねてグローにする
        for factor, opacity in ((8, 0.9), (3, 0.55)):
            small = body.scaled(max(1, body.width() // factor), max(1, body.height() // factor),
                                Qt.AspectRatioMode.IgnoreAspectRatio,
                                Qt.TransformationMode.SmoothTransformation)
            p.setOpacity(opacity)
            p.drawImage(rect, small)
        p.setOpacity(1.0)
        p.drawImage(rect, body)
        p.end()
        self._cache, self._cache_img = key, img
        return img

    def paintEvent(self, event):
        if self._flash and not self.flash_phase:
            return
        p = QPainter(self)
        p.drawImage(QRectF(0, 0, self.width(), self.height()), self._render())
        p.end()
