from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QColor

from app.ui import theme
from app.ui.digits import DigitDisplay, ghost_text
from app.ui.panel import PanelWidget, nine_slice_rects


def _count(img, pred):
    n = 0
    for y in range(0, img.height(), 2):
        for x in range(0, img.width(), 2):
            c = img.pixelColor(x, y)
            if pred(c):
                n += 1
    return n


def _is_red(c):
    return c.red() > 180 and c.green() < 120 and c.blue() < 140


def test_nine_slice_corners_keep_margin_size():
    pairs = nine_slice_rects(QSize(100, 60), QRect(0, 0, 400, 200), (10, 12, 14, 16))
    assert len(pairs) == 9
    dst, src = pairs[0]
    assert (dst.width(), dst.height()) == (10, 12) and src == QRect(0, 0, 10, 12)
    dst, src = pairs[8]  # 右下
    assert dst == QRect(386, 184, 14, 16) and src == QRect(86, 44, 14, 16)


def test_nine_slice_center_fills_rest():
    pairs = nine_slice_rects(QSize(100, 60), QRect(5, 5, 400, 200), (10, 10, 10, 10))
    dst, src = pairs[4]
    assert dst == QRect(15, 15, 380, 180) and src == QRect(10, 10, 80, 40)


def test_nine_slice_scale_shrinks_borders():
    pairs = nine_slice_rects(QSize(100, 60), QRect(0, 0, 400, 200), (40, 20, 40, 20), scale=0.5)
    dst, _ = pairs[0]
    assert (dst.width(), dst.height()) == (20, 10)


def test_nine_slice_never_overlaps_when_target_small():
    pairs = nine_slice_rects(QSize(100, 60), QRect(0, 0, 30, 20), (40, 20, 40, 20))
    tl, tr = pairs[0][0], pairs[2][0]
    assert tl.right() < tr.left()


def test_ghost_text_maps_digits_to_eight():
    assert ghost_text("-01:23.45") == "888:88.88"


def test_theme_fonts_load(qapp):
    assert "DSEG7" in theme.load_fonts()


def test_digit_display_draws_in_color(qtbot):
    d = DigitDisplay()
    qtbot.addWidget(d)
    d.resize(360, 90)
    d.set_text("00:12:34")
    d.set_color(QColor(theme.COLORS["red"]))
    assert _count(d.grab().toImage(), _is_red) > 30


def test_digit_display_flash_hides_digits(qtbot):
    d = DigitDisplay()
    qtbot.addWidget(d)
    d.resize(360, 90)
    d.set_text("00:12:34")
    d.set_color(QColor(theme.COLORS["red"]))
    d.set_flash(True)
    d.flash_phase = False  # 点滅の消灯側
    assert _count(d.grab().toImage(), _is_red) == 0


def test_panel_widget_paints_image(qtbot):
    p = PanelWidget(theme.asset("images/panel.png"), margins=(150, 120, 150, 120), scale=0.4)
    qtbot.addWidget(p)
    p.resize(500, 220)
    assert p.grab().toImage().pixelColor(250, 110).alpha() > 200


def test_panel_outline_draws_border_color(qtbot):
    p = PanelWidget(theme.asset("images/mini_panel.png"), margins=(110, 80, 110, 80), scale=0.3)
    qtbot.addWidget(p)
    p.resize(320, 124)
    assert _count(p.grab().toImage(), _is_red) == 0
    p.set_outline(QColor(theme.COLORS["red"]))
    assert _count(p.grab().toImage(), _is_red) > 40
    p.set_outline(None)
    assert _count(p.grab().toImage(), _is_red) == 0


def test_stylesheet_is_dark():
    css = theme.stylesheet()
    assert "QDialog" in css and theme.COLORS["bg"] in css
