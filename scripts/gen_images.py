"""デザイン画像の候補を Seedream 4.5（OpenRouter）で生成する。開発時のみ使う。

API キーは環境変数 OPENROUTER_API_KEY から読む（無ければ隣のフォルダの OpenRouter_Image_Studio/config.json。
どちらもこのリポジトリには書かない）。
候補は assets_ai/cand/<kind>_<n>.png に保存し、選定は人の目で行う。

実行: .venv\\Scripts\\python scripts\\gen_images.py [kind ...] [--n 5]
"""
import argparse
import base64
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAND = ROOT / "assets_ai" / "cand"
KEY_FILE = ROOT.parent / "OpenRouter_Image_Studio" / "config.json"
MODEL = "bytedance-seed/seedream-4.5"

COMMON = (
    "no text, no letters, no numbers, no digits, no logos, no watermark, "
    "straight-on orthographic front view, perfectly flat, symmetrical, crisp edges, "
    "the object isolated and centered on a plain flat uniform mid-grey studio background "
    "with an even margin around it, no shadow on the background"
)
PROMPTS = {
    "panel": (
        "16:9",
        "Faceplate of a futuristic sci-fi digital timer device. Dark gunmetal brushed "
        "aluminium frame with a thin bevel, subtle fine hexagon micro-texture, thin glowing "
        "cyan neon HUD trim lines and small angular corner brackets running along the outer "
        "border only. The large central area is a plain, uniform, very dark smoked-glass "
        "recess with no details. Premium industrial product render, moody low key lighting. "
        + COMMON,
    ),
    "mini": (
        "21:9",
        "Slim horizontal faceplate of a compact futuristic digital clock module. Dark "
        "gunmetal brushed metal rim with thin glowing cyan neon edge lines and tiny angular "
        "corner brackets on the border only. Wide plain uniform near-black smoked-glass "
        "window in the center with no details. Premium industrial product render. " + COMMON,
    ),
    "icon": (
        "1:1",
        "Application icon: a sleek futuristic digital stopwatch emblem on a dark gunmetal "
        "rounded square tile, a ring of glowing cyan neon segments around a small stopwatch "
        "crown button on top, bold simple silhouette readable at 32 pixels, rim light, "
        "centered, isolated on a plain flat uniform mid-grey background, no text, no numbers",
    ),
}


def load_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key and KEY_FILE.exists():
        key = json.loads(KEY_FILE.read_text(encoding="utf-8")).get("api_key", "").strip()
    if not key:
        sys.exit("API キーがありません: 環境変数 OPENROUTER_API_KEY を設定してください")
    return key


def generate(key: str, kind: str, index: int) -> Path:
    aspect, prompt = PROMPTS[kind]
    body = {"model": MODEL, "prompt": prompt, "aspect_ratio": aspect,
            "resolution": "2K", "output_format": "png"}
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/images", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as res:
        data = json.loads(res.read())
    raw = base64.b64decode(data["data"][0]["b64_json"], validate=True)
    out = CAND / f"{kind}_{index}.png"
    out.write_bytes(raw)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kinds", nargs="*", default=list(PROMPTS))
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--start", type=int, default=1)
    args = ap.parse_args()
    CAND.mkdir(parents=True, exist_ok=True)
    key = load_key()
    jobs = [(k, i) for k in args.kinds for i in range(args.start, args.start + args.n)]
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(generate, key, k, i): (k, i) for k, i in jobs}
        for f, (k, i) in futures.items():
            try:
                print("ok", f.result())
            except Exception as e:  # 1枚の失敗で他を止めない
                print("NG", k, i, e)


if __name__ == "__main__":
    main()
