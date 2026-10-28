"""タイマーの計算ロジック（UI から独立・時計は引数で受け取る）。

時間は「経過の積み上げ（accumulated）＋動いている間の now - started_at」で求める。
画面更新の回数に依存しないので、長時間動かしてもずれない。
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable

DAY = 86400.0
_TARGET_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class Kind(str, Enum):
    STOPWATCH = "stopwatch"
    COUNTDOWN = "countdown"
    POMODORO = "pomodoro"
    ALARM = "alarm"  # 時刻指定（例: 17:00 になったら鳴らす）


class State(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"


class Phase(str, Enum):
    WORK = "work"
    BREAK = "break"


@dataclass
class TimerSpec:
    id: str
    kind: Kind
    name: str
    color: str
    duration: float = 0
    repeat: bool = False
    work: float = 0
    rest: float = 0
    sets: int = 0
    sound: bool = True
    target: str = ""  # 時刻指定の "HH:MM"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "TimerSpec":
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in d.items() if k in known}
        data["kind"] = Kind(data["kind"])
        return cls(**data)


def seconds_until(target: str, wall: datetime, min_ahead: float = 0) -> float:
    """wall から次に target（"HH:MM"）になるまでの秒数。今ちょうど・過ぎていたら翌日。
    min_ahead 秒以内に迫っているときも翌日にする（鳴った直後の時計のずれで二度鳴らないように）。"""
    h, m = (int(x) for x in target.split(":"))
    goal = wall.replace(hour=h, minute=m, second=0, microsecond=0)
    while (goal - wall).total_seconds() <= min_ahead:
        goal += timedelta(days=1)
    return (goal - wall).total_seconds()


def validate(spec: TimerSpec) -> str | None:
    """作成できない設定ならエラー文言を返す。問題なければ None。"""
    if not spec.name.strip():
        return "名前を入力してください"
    if spec.kind == Kind.COUNTDOWN and spec.duration <= 0:
        return "時間を1秒以上にしてください"
    if spec.kind == Kind.POMODORO:
        if spec.work <= 0:
            return "作業時間を1秒以上にしてください"
        if spec.rest <= 0:
            return "休憩時間を1秒以上にしてください"
        if spec.sets < 0:
            return "セット数は0以上にしてください"
    if spec.kind == Kind.ALARM and not _TARGET_RE.match(spec.target or ""):
        return "時刻を 00:00〜23:59 で指定してください"
    return None


@dataclass
class Event:
    timer_id: str
    type: str  # "finished" | "repeat" | "phase"
    count: int = 1
    phase: Phase | None = None
    late: float = 0  # 時刻指定が、予定の時刻から何秒遅れて鳴ったか（アプリを閉じていた等）


class TimerRuntime:
    # 時刻指定で「今何時か」を知るための時計（テストで差し替える）。
    # 時刻指定は経過時間ではなくこの時計で鳴らすので、PC の時刻合わせにも追従する
    wall_clock: Callable[[], datetime] = datetime.now

    def __init__(self, spec: TimerSpec):
        self.spec = spec
        self.laps: list[float] = []
        self.rearm = False  # 保存時に動いていた時刻指定。起動後に resume() で同じ時刻のまま再開する
        self.reset()

    # ---- 状態 ----
    def reset(self) -> None:
        self.state = State.IDLE
        self.accumulated = 0.0
        self.started_at: float | None = None
        self.laps = []
        self.cycles = 0
        self.phase = Phase.WORK
        self.set_index = 0
        self.length: float | None = None  # 時刻指定の、開始（再開）時点から目標時刻までの秒数
        self.fire_at: datetime | None = None  # 時刻指定が鳴る日時
        self.armed_at: datetime | None = None  # 時刻指定を動かし始めた日時（進捗バーの起点）

    def phase_length(self) -> float | None:
        if self.spec.kind == Kind.COUNTDOWN:
            return float(self.spec.duration)
        if self.spec.kind == Kind.POMODORO:
            return float(self.spec.work if self.phase == Phase.WORK else self.spec.rest)
        if self.spec.kind == Kind.ALARM:
            if self.length is None:  # 未開始: 今から目標時刻まで
                return seconds_until(self.spec.target, self.wall_clock())
            return self.length
        return None

    def _retarget(self, now: float, min_ahead: float = 0) -> None:
        wall = self.wall_clock()
        self.length = seconds_until(self.spec.target, wall, min_ahead)
        self.fire_at = wall + timedelta(seconds=self.length)
        self.accumulated = 0.0
        self.started_at = now

    def elapsed(self, now: float) -> float:
        if self.started_at is None:
            return self.accumulated
        if self.spec.kind == Kind.ALARM and self.fire_at is not None and self.length is not None:
            return self.length - (self.fire_at - self.wall_clock()).total_seconds()
        return self.accumulated + (now - self.started_at)

    def remaining(self, now: float) -> float | None:
        length = self.phase_length()
        if length is None:
            return None
        return max(0.0, length - self.elapsed(now))

    def overtime(self, now: float) -> float:
        length = self.phase_length()
        if self.state != State.FINISHED or length is None:
            return 0.0
        return max(0.0, self.elapsed(now) - length)

    def progress(self, now: float) -> float:
        if self.spec.kind == Kind.ALARM and self.armed_at and self.fire_at:
            # 動かし始めてから鳴る時刻までのうち、どこまで来たか（一時停止・再起動しても戻らない）
            total = (self.fire_at - self.armed_at).total_seconds()
            remaining = self.remaining(now) or 0.0
            return min(1.0, max(0.0, 1 - remaining / total)) if total > 0 else 1.0
        length = self.phase_length()
        if not length:
            return 0.0
        return min(1.0, max(0.0, self.elapsed(now) / length))

    # ---- 操作 ----
    def start(self, now: float) -> None:
        if self.state == State.FINISHED:
            self.reset()
        if self.state in (State.IDLE, State.PAUSED):
            self.started_at = now
            self.state = State.RUNNING
            if self.spec.kind == Kind.ALARM:
                before = self.fire_at
                self._retarget(now)  # 一時停止のあいだに時刻が進んでいても、目標時刻に合わせ直す
                if self.armed_at is None or before is None or self.fire_at != before:
                    # 初めて動かした、または止めている間に鳴る時刻を過ぎて翌日に回った → 新しい周
                    self.armed_at = self.wall_clock()
            self.rearm = False

    def resume(self, now: float) -> None:
        """保存時に動いていた時刻指定を、同じ鳴る時刻のまま再開する（過ぎていれば次の tick で鳴る）。"""
        if self.fire_at is None or self.length is None:
            self.start(now)
            return
        self.state = State.RUNNING
        self.started_at = now
        self.rearm = False

    def pause(self, now: float) -> None:
        if self.state != State.RUNNING:
            return
        self.accumulated = self.elapsed(now)
        self.started_at = None
        self.state = State.PAUSED

    def lap(self, now: float) -> float | None:
        if self.state != State.RUNNING or self.spec.kind == Kind.ALARM:
            return None
        value = self.elapsed(now)
        self.laps.append(value)
        return value

    def skip(self, now: float) -> None:
        """ポモドーロの現フェーズを飛ばす（お知らせは出さない）。"""
        if self.spec.kind != Kind.POMODORO or self.state == State.FINISHED:
            return
        self.accumulated = 0.0
        if self.started_at is not None:
            self.started_at = now
        if self.phase == Phase.WORK:
            self.phase = Phase.BREAK
        else:
            self.set_index += 1
            self.phase = Phase.WORK
            if self.spec.sets and self.set_index >= self.spec.sets:
                self.state = State.FINISHED
                self.phase = Phase.BREAK
                self.accumulated = float(self.spec.rest)
                self.started_at = now

    def tick(self, now: float) -> list[Event]:
        if self.state != State.RUNNING:
            return []
        if self.spec.kind == Kind.COUNTDOWN:
            return self._tick_countdown(now)
        if self.spec.kind == Kind.POMODORO:
            return self._tick_pomodoro(now)
        if self.spec.kind == Kind.ALARM:
            return self._tick_alarm(now)
        return []

    def _tick_alarm(self, now: float) -> list[Event]:
        late = self.elapsed(now) - (self.length or 0)
        if late < 0:
            return []
        if self.spec.repeat:
            # 毎日: 翌日の同じ時刻に合わせ直す（何日分過ぎていても、お知らせは1回）。
            # 60秒以内の同じ時刻は翌日扱いにして、時計が少し戻されても二度鳴らないようにする
            self.cycles += 1
            self.armed_at = self.wall_clock()
            self._retarget(now, min_ahead=60)
            return [Event(self.spec.id, "repeat", late=late)]
        self.state = State.FINISHED
        return [Event(self.spec.id, "finished", late=late)]

    def _tick_countdown(self, now: float) -> list[Event]:
        length = float(self.spec.duration)
        e = self.elapsed(now)
        if e < length:
            return []
        if self.spec.repeat:
            n = math.floor(e / length)
            self.cycles += n
            # 開始位置を周回数ぶんずらす（余りはそのまま次の周に持ち越す）
            self.accumulated -= n * length
            return [Event(self.spec.id, "repeat", count=n)]
        self.state = State.FINISHED
        return [Event(self.spec.id, "finished")]

    def _tick_pomodoro(self, now: float) -> list[Event]:
        switches = 0
        while True:
            length = float(self.spec.work if self.phase == Phase.WORK else self.spec.rest)
            if self.elapsed(now) < length:
                break
            if self.phase == Phase.BREAK:
                self.set_index += 1
                if self.spec.sets and self.set_index >= self.spec.sets:
                    # 経過はそのまま残し、超過時間として数え続ける
                    self.state = State.FINISHED
                    return [Event(self.spec.id, "finished")]
            self.accumulated -= length
            self.phase = Phase.BREAK if self.phase == Phase.WORK else Phase.WORK
            switches += 1
        if not switches:
            return []
        # スリープ明けなどで何回分も進んだときも、お知らせは1回にまとめる
        return [Event(self.spec.id, "phase", count=switches, phase=self.phase)]

    # ---- 保存 ----
    def to_dict(self, now: float) -> dict:
        return {
            "spec": self.spec.to_dict(),
            "state": self.state.value,
            "elapsed": self.elapsed(now),
            "laps": list(self.laps),
            "cycles": self.cycles,
            "phase": self.phase.value,
            "set_index": self.set_index,
            "length": self.length,
            "fire_at": self.fire_at.isoformat() if self.fire_at else None,
            "armed_at": self.armed_at.isoformat() if self.armed_at else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TimerRuntime":
        """保存データから復元する。動いていたものは一時停止で、終了済みは初期状態で戻す。"""
        r = cls(TimerSpec.from_dict(d["spec"]))
        state = State(d.get("state", "idle"))
        if state in (State.RUNNING, State.PAUSED):
            r.state = State.PAUSED
            r.accumulated = float(d.get("elapsed", 0.0))
            r.laps = [float(x) for x in d.get("laps", [])]
            r.cycles = int(d.get("cycles", 0))
            r.phase = Phase(d.get("phase", "work"))
            r.set_index = int(d.get("set_index", 0))
            if r.spec.kind == Kind.ALARM:
                length = d.get("length")
                r.length = float(length) if length is not None else None
                fire_at = d.get("fire_at")
                r.fire_at = datetime.fromisoformat(fire_at) if fire_at else None
                armed_at = d.get("armed_at")
                r.armed_at = datetime.fromisoformat(armed_at) if armed_at else None
                r.rearm = state == State.RUNNING
        return r
