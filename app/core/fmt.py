"""時間の表示用フォーマット。"""
import math

_EPS = 1e-6


def format_clock(seconds: float, centis: bool = False, ceil: bool = False) -> str:
    """秒数を ``HH:MM:SS``（centis=True なら ``HH:MM:SS.cs``）にする。

    既定は切り捨て（ストップウォッチ向け）。ceil=True はカウントダウン向けで、
    残り 0.4 秒を 00:00:01 と見せ、00:00:00 は本当に 0 になったときだけ出す。
    負値は先頭に ``-`` を付ける（終了後の超過時間）。
    """
    sign = "-" if seconds < 0 else ""
    s = abs(seconds)
    if centis:
        total_cs = math.floor(round(s * 100, 6))
        whole, cs = divmod(total_cs, 100)
    else:
        whole = math.ceil(s - _EPS) if ceil else math.floor(s + _EPS)
        cs = None
    h, rem = divmod(int(whole), 3600)
    m, sec = divmod(rem, 60)
    text = f"{sign}{h:02d}:{m:02d}:{sec:02d}"
    if cs is not None:
        text += f".{cs:02d}"
    return text
