import wave
from pathlib import Path
from typing import cast

import pytest
from PIL import Image
from PySide6.QtGui import QFontDatabase

ROOT = Path(__file__).resolve().parents[1] / "assets"
SOUNDS = ["chime", "beep", "digital"]


@pytest.mark.parametrize("name", SOUNDS)
def test_sound_format(name):
    with wave.open(str(ROOT / "sounds" / f"{name}.wav")) as w:
        assert (w.getframerate(), w.getsampwidth(), w.getnchannels()) == (44100, 2, 1)
        assert 0.3 <= w.getnframes() / w.getframerate() <= 1.5


def test_fonts_and_license_present():
    assert (ROOT / "fonts" / "DSEG7Classic-Bold.ttf").exists()
    assert (ROOT / "fonts" / "DSEG7Classic-Regular.ttf").exists()
    assert "SIL OPEN FONT LICENSE" in (ROOT / "fonts" / "OFL.txt").read_text(encoding="utf-8").upper()


def test_font_loads_in_qt(qapp):
    fid = QFontDatabase.addApplicationFont(str(ROOT / "fonts" / "DSEG7Classic-Bold.ttf"))
    assert fid >= 0
    assert any("DSEG7" in f for f in QFontDatabase.applicationFontFamilies(fid))


@pytest.mark.parametrize("name,min_w", [("panel.png", 1024), ("mini_panel.png", 1024), ("icon.png", 256)])
def test_images(name, min_w):
    with Image.open(ROOT / "images" / name) as im:
        assert im.width >= min_w


def test_mini_panel_has_no_floor_shadow():
    # 床の影（明るい無彩色の灰色）が残ると、ミニ表示の下に灰色の帯が出る
    with Image.open(ROOT / "images" / "mini_panel.png") as im:
        rgba = im.convert("RGBA")
    w, h = rgba.size
    bottom = rgba.crop((0, h - h // 10, w, h))
    gray = sum(1 for y in range(bottom.height) for x in range(w)
               if (p := cast("tuple[int, int, int, int]", bottom.getpixel((x, y))))[3] > 128
               and max(p[:3]) - min(p[:3]) < 12 and max(p[:3]) > 120)
    assert gray < w  # 金属の縁のハイライトが少し入る（影ありの旧画像は約 9000）


def test_mini_panel_window_is_centered():
    # 影の分だけ画像が右に広いと、9スライスで描いたときにガラス面が左に寄り、数字が右にずれて見える
    with Image.open(ROOT / "images" / "mini_panel.png") as im:
        rgba = im.convert("RGBA")
    w, h = rgba.size
    row = [cast("tuple[int, int, int, int]", rgba.getpixel((x, h // 2))) for x in range(w)]
    groove = [x for x in range(w) if row[x][3] > 128 and max(row[x][:3]) < 15]  # ガラス面のふちの暗い溝
    left, right = groove[0], groove[-1]
    assert abs((left + right) / 2 - w / 2) <= w * 0.01


def test_icon_sizes():
    with Image.open(ROOT / "images" / "icon.ico") as im:
        sizes = set(im.info["sizes"])
    assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= sizes
