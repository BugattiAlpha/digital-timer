"""タイマーの状態から「何をどの色で出すか」を決める（描画しない純粋関数）。"""
from __future__ import annotations

from dataclasses import dataclass

from ..core.fmt import format_clock
from ..core.timers import Kind, Phase, State, TimerRuntime

WARN_SECONDS = 60
KIND_LABELS = {Kind.STOPWATCH: "ストップウォッチ", Kind.COUNTDOWN: "カウントダウン",
               Kind.POMODORO: "ポモドーロ", Kind.ALARM: "時刻指定"}


@dataclass
class Display:
    text: str
    color: str  # タイマー色の名前、または "amber" / "red"
    status: str
    progress: float


def _status(r: TimerRuntime) -> str:
    parts = [KIND_LABELS[r.spec.kind]]
    if r.spec.kind == Kind.COUNTDOWN and r.spec.repeat:
        parts.append(f"繰り返し {r.cycles}回" if r.cycles else "繰り返し")
    if r.spec.kind == Kind.POMODORO:
        total = str(r.spec.sets) if r.spec.sets else "∞"
        current = min(r.set_index + 1, r.spec.sets) if r.spec.sets else r.set_index + 1
        label = "作業" if r.phase == Phase.WORK else "休憩"
        parts.append(f"{label} {current}/{total}")
    if r.spec.kind == Kind.ALARM:
        parts.append(r.spec.target)
        if r.spec.repeat:
            parts.append("毎日")
    if r.state == State.PAUSED:
        parts.append("一時停止中")
    elif r.state == State.IDLE and r.spec.kind == Kind.ALARM:
        parts.append("停止中")  # 残りの表示は動いて見えるが鳴らないので、はっきり書く
    elif r.state == State.FINISHED:
        parts.append("終了")
    return " · ".join(parts)


def display_state(r: TimerRuntime, now: float) -> Display:
    status = _status(r)
    if r.spec.kind == Kind.STOPWATCH:
        return Display(format_clock(r.elapsed(now), centis=True), r.spec.color, status, 0.0)
    if r.state == State.FINISHED:
        return Display(format_clock(-r.overtime(now)), "red", status, 1.0)
    remaining = r.remaining(now) or 0.0
    color = r.spec.color
    if r.state != State.IDLE and remaining < WARN_SECONDS:
        color = "amber"
    return Display(format_clock(remaining, ceil=True), color, status, r.progress(now))
