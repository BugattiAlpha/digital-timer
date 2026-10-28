"""選定した生成画像から灰色の背景を取り除き、透過 PNG として assets/images に書き出す。

背景は「均一な灰色（緩いグラデーション）」で生成しているので、
四隅の色から背景の推定画像を作り、差が小さく外周とつながっている領域を背景とみなす。

実行: .venv\\Scripts\\python scripts\\cutout.py
"""
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
CAND = ROOT / "assets_ai" / "cand"
OUT = ROOT / "assets" / "images"

# (候補, 出力名, 出力の横幅, 背景の判定方法)
# "corners": 四隅の色からの差で判定（背景が素直なグラデーション）
# "octagon": 面取りした長方形として外形を測り、多角形で切り抜く（背景が放射状のビネットで、
#            縁のヘアライン金属が背景と同じ明るさのため色では分けられないパネル用）
# "octagon_footed": octagon と同じだが、本体の下に台座と床の影がある画像用。台座と影は切り捨てる
#            （"corners" だと影が物体扱いで残り、下に灰色の帯が出て、右の影の分だけ数字が右にずれた）
SELECTED = [
    ("panel_3", "panel", 1600, "octagon"),
    ("mini_4", "mini_panel", 1200, "octagon_footed"),
    ("icon_1", "icon", 512, "corners"),
]
# 背景とみなす明るさの範囲（候補ごと。mini は背景の灰色が明るい）
BANDS = {"panel_3": (70, 135), "mini_4": (115, 186)}
THRESHOLD = 18


def _num(v: Any) -> float:
    """Image.point に渡す関数の引数（実際は画素値の数値。型定義が広いので明示する）。"""
    return v


def background_estimate(im: Image.Image) -> Image.Image:
    w, h = im.size
    s = 24  # 四隅から少し内側の小領域の平均色
    def avg(x, y):
        return im.crop((x, y, x + s, y + s)).resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
    corners = Image.new("RGB", (2, 2))
    corners.putdata([avg(4, 4), avg(w - s - 4, 4), avg(4, h - s - 4), avg(w - s - 4, h - s - 4)])
    return corners.resize((w, h), Image.Resampling.BILINEAR)


def _first_out_of_band(values, band) -> int:
    for i, v in enumerate(values):
        if not band[0] <= v <= band[1]:
            return i
    raise ValueError("外形が見つかりません")


def octagon_mask(im: Image.Image, band, footed: bool = False) -> Image.Image:
    """中央の縦横の線で外形の上下左右を測り、上端すぐ下の行で面取り量を測る。
    footed のときは、下端を中央ではなく面取りのすぐ内側（台座より外）の縦線で測る。"""
    lum = im.convert("L").filter(ImageFilter.MedianFilter(5))
    w, h = lum.size
    row = [lum.getpixel((x, h // 2)) for x in range(w)]
    col = [lum.getpixel((w // 2, y)) for y in range(h)]
    left, right = _first_out_of_band(row, band), w - 1 - _first_out_of_band(row[::-1], band)
    top = _first_out_of_band(col, band)
    probe = [lum.getpixel((x, top + 3)) for x in range(left, w // 2)]
    c = _first_out_of_band(probe, band)
    if footed:
        x = left + c + 20
        col = [lum.getpixel((x, y)) for y in range(h)]
    # 床の影は背景より暗いが範囲内なので、下から見て最初に範囲外になる所が本体の下端
    bottom = h - 1 - _first_out_of_band(col[::-1], band)
    k = 4  # 4倍で描いて縮小し、縁をなめらかにする
    big = Image.new("L", (w * k, h * k), 0)
    pts = [(left + c, top), (right - c, top), (right, top + c), (right, bottom - c),
           (right - c, bottom), (left + c, bottom), (left, bottom - c), (left, top + c)]
    ImageDraw.Draw(big).polygon([(x * k, y * k) for x, y in pts], fill=255)
    return big.resize((w, h), Image.Resampling.BOX)


def object_mask(im: Image.Image, method: str, band=None) -> Image.Image:
    if method in ("octagon", "octagon_footed"):
        return octagon_mask(im, band, footed=method == "octagon_footed")
    else:
        diff = ImageChops.difference(im, background_estimate(im)).convert("L")
        diff = diff.filter(ImageFilter.MedianFilter(5))
        fg = diff.point(lambda v: 255 if _num(v) > THRESHOLD else 0)
    # 外周から背景を塗りつぶす → 物体の内側の暗い部分は背景扱いにならない
    marker = fg.copy()
    w, h = marker.size
    for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if marker.getpixel((x, y)) == 0:
            ImageDraw.floodfill(marker, (x, y), 128)
    mask = marker.point(lambda v: 0 if v == 128 else 255)
    # 1px 内側に寄せて灰色のにじみを消し、縁を少しぼかしてアンチエイリアスにする
    mask = mask.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(1.2))
    return mask


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for cand, name, width, method in SELECTED:
        im = Image.open(CAND / f"{cand}.png").convert("RGB")
        mask = object_mask(im, method, BANDS.get(cand))
        rgba = im.copy()
        rgba.putalpha(mask)
        bbox = mask.point(lambda v: 255 if _num(v) > 8 else 0).getbbox()
        rgba = rgba.crop(bbox)
        height = round(rgba.height * width / rgba.width)
        rgba = rgba.resize((width, height), Image.Resampling.LANCZOS)
        rgba.save(OUT / f"{name}.png")
        print(name, rgba.size)


if __name__ == "__main__":
    main()
