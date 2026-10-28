from app.core.timers import Kind, Phase, State, TimerRuntime, TimerSpec, validate


def sw():
    return TimerSpec(id="s", kind=Kind.STOPWATCH, name="SW", color="cyan")


def cd(duration, repeat=False):
    return TimerSpec(id="c", kind=Kind.COUNTDOWN, name="CD", color="cyan",
                     duration=duration, repeat=repeat)


def pomo(work, rest, sets=0):
    return TimerSpec(id="p", kind=Kind.POMODORO, name="PO", color="cyan",
                     work=work, rest=rest, sets=sets)


def test_stopwatch_pause_resume():
    t = TimerRuntime(sw())
    t.start(0)
    t.pause(10)
    t.start(100)
    assert t.elapsed(105) == 15


def test_stopwatch_never_finishes():
    t = TimerRuntime(sw())
    t.start(0)
    assert t.tick(10 ** 6) == []
    assert t.state == State.RUNNING


def test_countdown_finishes_and_counts_overtime():
    t = TimerRuntime(cd(60))
    t.start(0)
    assert t.tick(59) == []
    ev = t.tick(61)
    assert [e.type for e in ev] == ["finished"]
    assert t.state == State.FINISHED
    assert t.overtime(70) == 10
    assert t.tick(80) == []


def test_countdown_remaining_and_progress():
    t = TimerRuntime(cd(100))
    t.start(0)
    assert t.remaining(25) == 75
    assert t.progress(25) == 0.25


def test_countdown_repeat_no_drift_and_single_event_after_long_gap():
    t = TimerRuntime(cd(60, repeat=True))
    t.start(0)
    ev = t.tick(60 * 5 + 1)
    assert len(ev) == 1
    assert ev[0].type == "repeat" and ev[0].count == 5
    assert t.cycles == 5
    assert t.remaining(60 * 5 + 1) == 59
    assert t.state == State.RUNNING


def test_countdown_repeat_counts_each_cycle():
    t = TimerRuntime(cd(10, repeat=True))
    t.start(0)
    assert t.tick(10)[0].count == 1
    assert t.tick(20)[0].count == 1
    assert t.cycles == 2


def test_reset_returns_to_idle():
    t = TimerRuntime(cd(60, repeat=True))
    t.start(0)
    t.tick(130)
    t.reset()
    assert t.state == State.IDLE and t.cycles == 0 and t.remaining(500) == 60


def test_pomodoro_alternates_and_ends_after_sets():
    t = TimerRuntime(pomo(work=25 * 60, rest=5 * 60, sets=2))
    t.start(0)
    assert t.phase == Phase.WORK
    assert t.tick(25 * 60)[0].phase == Phase.BREAK
    ev = t.tick(30 * 60)
    assert ev[0].phase == Phase.WORK and t.set_index == 1
    t.tick(55 * 60)
    ev = t.tick(60 * 60)
    assert ev[-1].type == "finished"
    assert t.state == State.FINISHED


def test_pomodoro_infinite_sets_keeps_going():
    t = TimerRuntime(pomo(work=10, rest=5, sets=0))
    t.start(0)
    for now in range(10, 1000, 5):
        for e in t.tick(now):
            assert e.type == "phase"
    assert t.state == State.RUNNING


def test_pomodoro_long_gap_gives_single_event():
    t = TimerRuntime(pomo(work=10, rest=5, sets=0))
    t.start(0)
    ev = t.tick(47)  # 3周（6回切替）して WORK の2秒目
    assert len(ev) == 1
    assert ev[0].count == 6 and ev[0].phase == Phase.WORK
    assert t.remaining(47) == 8


def test_pomodoro_skip_moves_phase_without_event():
    t = TimerRuntime(pomo(work=100, rest=50))
    t.start(0)
    t.skip(30)
    assert t.phase == Phase.BREAK
    assert t.tick(31) == []
    assert t.remaining(40) == 40


def test_lap_records_total_times():
    t = TimerRuntime(sw())
    t.start(0)
    t.lap(5)
    t.lap(12)
    assert t.laps == [5, 12]


def test_lap_ignored_when_not_running():
    t = TimerRuntime(sw())
    assert t.lap(5) is None
    assert t.laps == []


def test_roundtrip_running_restores_paused():
    t = TimerRuntime(cd(60))
    t.start(0)
    r = TimerRuntime.from_dict(t.to_dict(20))
    assert r.state == State.PAUSED
    assert r.remaining(999) == 40
    assert r.spec == t.spec


def test_roundtrip_finished_restores_idle():
    t = TimerRuntime(cd(60))
    t.start(0)
    t.tick(70)
    r = TimerRuntime.from_dict(t.to_dict(80))
    assert r.state == State.IDLE and r.remaining(0) == 60


def test_roundtrip_pomodoro_phase_and_laps():
    t = TimerRuntime(pomo(work=10, rest=5, sets=3))
    t.start(0)
    t.tick(12)
    r = TimerRuntime.from_dict(t.to_dict(12))
    assert r.phase == Phase.BREAK and r.remaining(0) == 3


def test_validate_rejects_zero():
    assert validate(cd(0))
    assert validate(pomo(work=0, rest=60))
    assert validate(pomo(work=60, rest=0))
    assert validate(cd(60)) is None
    assert validate(sw()) is None


def test_validate_rejects_empty_name():
    s = cd(60)
    s.name = "  "
    assert validate(s)


# ---- 時刻指定 ----
from datetime import datetime, timedelta  # noqa: E402

from app.core.timers import seconds_until  # noqa: E402


def alarm(target="17:00", repeat=False):
    return TimerSpec(id="a", kind=Kind.ALARM, name="AL", color="cyan", target=target, repeat=repeat)


class Wall:
    """動かせる壁時計（実際の時刻）。"""

    def __init__(self, h, m, s=0):
        self.t = datetime(2026, 10, 29, h, m, s)

    def __call__(self):
        return self.t

    def add(self, seconds):
        self.t += timedelta(seconds=seconds)


def armed(target="17:00", repeat=False, at=(16, 30)):
    t = TimerRuntime(alarm(target, repeat))
    wall = Wall(*at)
    t.wall_clock = wall
    t.start(0)
    return t, wall


def test_seconds_until_today_or_tomorrow():
    assert seconds_until("17:00", datetime(2026, 10, 29, 16, 30)) == 1800
    assert seconds_until("09:00", datetime(2026, 10, 29, 17, 0)) == 16 * 3600  # 過ぎていたら翌日
    assert seconds_until("17:00", datetime(2026, 10, 29, 17, 0)) == 86400
    assert seconds_until("17:00", datetime(2026, 10, 29, 16, 59, 30), min_ahead=60) == 86430


def test_alarm_counts_down_to_clock_time_then_overtime():
    t, w = armed()
    assert t.remaining(0) == 1800
    w.add(1799)
    assert t.tick(1799) == []
    w.add(1)
    assert [e.type for e in t.tick(1800)] == ["finished"]
    w.add(10)
    assert t.state == State.FINISHED and t.overtime(1810) == 10


def test_alarm_follows_wall_clock_not_elapsed_time():
    # PC の時計が進められた（時刻合わせ）ら、経過時間に関係なくその時刻で鳴る
    t, w = armed()
    w.add(1800)
    assert [e.type for e in t.tick(5)] == ["finished"]


def test_alarm_idle_shows_time_until_target():
    t = TimerRuntime(alarm())
    t.wall_clock = Wall(16, 0)
    assert t.remaining(0) == 3600 and t.progress(0) == 0


def test_alarm_pause_freezes_and_resume_retargets():
    t, w = armed(at=(16, 0))
    w.add(600)
    t.pause(600)
    w.add(2400)
    assert t.remaining(3000) == 3000  # 一時停止中は止まる
    assert t.tick(3000) == []
    t.start(3000)
    assert t.remaining(3000) == 600  # 再開すると時刻に合わせ直す


def test_alarm_daily_repeat_rearms_for_tomorrow():
    t, w = armed(repeat=True, at=(16, 59))
    w.add(60)
    ev = t.tick(60)
    assert ev[0].type == "repeat" and t.state == State.RUNNING and t.cycles == 1
    assert (t.remaining(60) or 0) > 86000  # 直後にもう一度鳴らず、翌日に合わせる
    w.t = datetime(2026, 10, 29, 16, 0)  # 時計が大きく戻されても同じ日にもう一度は鳴らない
    assert t.tick(61) == []


def test_alarm_validate_target():
    assert validate(alarm(""))
    assert validate(alarm("25:00"))
    assert validate(alarm("ab:cd"))
    assert validate(alarm("07:05")) is None


def test_alarm_restore_keeps_fire_time():
    t, w = armed(at=(16, 0))
    d = t.to_dict(10)
    r = TimerRuntime.from_dict(d)
    r.wall_clock = Wall(16, 30)  # 30分後に起動
    assert r.state == State.PAUSED and r.rearm
    r.resume(0)
    assert r.state == State.RUNNING and r.remaining(0) == 1800  # 時刻は同じ 17:00 のまま


def test_alarm_missed_while_closed_fires_late_once():
    t, w = armed(at=(16, 0))
    r = TimerRuntime.from_dict(t.to_dict(10))
    r.wall_clock = Wall(18, 0)  # 閉じている間に 17:00 を過ぎた
    r.resume(0)
    ev = r.tick(0)
    assert [e.type for e in ev] == ["finished"] and ev[0].late == 3600


def test_alarm_paused_restore():
    p, _ = armed(at=(16, 0))
    p.pause(600)
    q = TimerRuntime.from_dict(p.to_dict(600))
    assert q.remaining(0) == 3600 and not q.rearm


def test_alarm_ignores_lap():
    t, w = armed()
    assert t.lap(10) is None and t.laps == []


def test_alarm_progress_survives_pause_and_restart():
    # 一時停止・再起動しても進捗バーが 0 に戻らない（16:00 に 17:00 を設定した例）
    t, w = armed(at=(16, 0))
    w.add(1800)
    assert t.progress(1800) == 0.5
    t.pause(1800)
    assert t.progress(1800) == 0.5
    w.add(600)
    t.start(2400)
    assert abs(t.progress(2400) - 2400 / 3600) < 1e-9
    r = TimerRuntime.from_dict(t.to_dict(2400))
    r.wall_clock = w
    r.resume(0)
    assert abs(r.progress(0) - 2400 / 3600) < 1e-9


def test_alarm_progress_restarts_when_pause_spans_target():
    # 9:00 に 10:00 で動かし、9:30 に止めて翌日 9:00 に再開 → 新しい周として 0 から
    t, w = armed(target="10:00", at=(9, 0))
    w.add(1800)
    t.pause(1800)
    w.add(86400 - 1800)
    t.start(5000)
    assert t.progress(5000) == 0
