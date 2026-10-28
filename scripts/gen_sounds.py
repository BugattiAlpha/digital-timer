"""アラーム音3種をサイン波合成で作る（外部素材を使わない）。

実行: .venv\\Scripts\\python scripts\\gen_sounds.py
"""
import math
import struct
import wave
from pathlib import Path

RATE = 44100
OUT = Path(__file__).resolve().parents[1] / "assets" / "sounds"


def tone(freq, dur, decay=6.0, harmonics=((1, 1.0),), square=0.0):
    n = int(RATE * dur)
    out = []
    for i in range(n):
        t = i / RATE
        env = math.exp(-decay * t) * min(1.0, t / 0.005)  # 5ms のアタックでクリック音を防ぐ
        v = sum(a * math.sin(2 * math.pi * freq * h * t) for h, a in harmonics)
        if square:
            v = (1 - square) * v + square * math.copysign(1.0, v)
        out.append(v * env)
    return out


def silence(dur):
    return [0.0] * int(RATE * dur)


def write(name, samples):
    peak = max(abs(s) for s in samples) or 1.0
    frames = b"".join(struct.pack("<h", int(s / peak * 0.85 * 32767)) for s in samples)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(frames)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bell = ((1, 1.0), (2.76, 0.35), (5.4, 0.12))
    # chime: 高→低の2音ベル
    write("chime", tone(1318.5, 0.35, 5, bell) + tone(987.8, 0.65, 4, bell))
    # beep: 角のある短いブザー2回
    b = tone(880, 0.14, 2, square=0.5)
    write("beep", b + silence(0.08) + b + silence(0.2))
    # digital: 腕時計風の3連ピッ
    p = tone(2093, 0.06, 1, square=0.3)
    write("digital", p + silence(0.07) + p + silence(0.07) + p + silence(0.35))


if __name__ == "__main__":
    main()
