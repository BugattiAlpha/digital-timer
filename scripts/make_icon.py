"""assets/images/icon.png を正方形に揃え、Windows 用の icon.ico を作る。

実行: .venv\\Scripts\\python scripts\\make_icon.py（cutout.py の後）
"""
from pathlib import Path

from PIL import Image

IMAGES = Path(__file__).resolve().parents[1] / "assets" / "images"
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main():
    im = Image.open(IMAGES / "icon.png").convert("RGBA")
    side = max(im.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(im, ((side - im.width) // 2, (side - im.height) // 2))
    square.save(IMAGES / "icon.png")
    square.save(IMAGES / "icon.ico", sizes=SIZES)


if __name__ == "__main__":
    main()
