from app.core.timers import Kind, TimerRuntime, TimerSpec
from app.ui.display import display_state


def rt(kind, **kw):
    return TimerRuntime(TimerSpec(id="x", kind=kind, name="n", color="green", **kw))


def test_stopwatch_shows_centis_in_timer_color():
    r = rt(Kind.STOPWATCH)
    r.start(0)
    d = display_state(r, 65.5)
    assert d.text == "00:01:05.50" and d.color == "green" and d.progress == 0


def test_countdown_rounds_up_remaining():
    r = rt(Kind.COUNTDOWN, duration=300)
    r.start(0)
    d = display_state(r, 0.5)
    assert d.text == "00:05:00" and d.color == "green"
    assert abs(d.progress - 0.5 / 300) < 1e-9


def test_countdown_last_minute_turns_amber():
    r = rt(Kind.COUNTDOWN, duration=300)
    r.start(0)
    assert display_state(r, 241).color == "amber"
    assert display_state(r, 239).color == "green"


def test_idle_short_countdown_is_not_amber():
    r = rt(Kind.COUNTDOWN, duration=30)
    assert display_state(r, 0).color == "green"


def test_finished_countdown_shows_red_overtime():
    r = rt(Kind.COUNTDOWN, duration=60)
    r.start(0)
    r.tick(61)
    d = display_state(r, 72.3)
    assert d.text == "-00:00:12" and d.color == "red"
    assert "終了" in d.status


def test_repeat_countdown_status_shows_cycles():
    r = rt(Kind.COUNTDOWN, duration=10, repeat=True)
    r.start(0)
    r.tick(25)
    assert "2回" in display_state(r, 25).status


def test_pomodoro_status_shows_phase_and_set():
    r = rt(Kind.POMODORO, work=60, rest=30, sets=4)
    r.start(0)
    assert "作業 1/4" in display_state(r, 10).status
    r.tick(60)
    assert "休憩 1/4" in display_state(r, 61).status


def test_pomodoro_infinite_sets_status():
    r = rt(Kind.POMODORO, work=60, rest=30, sets=0)
    assert "作業 1/∞" in display_state(r, 0).status


def test_paused_status():
    r = rt(Kind.STOPWATCH)
    r.start(0)
    r.pause(5)
    assert "一時停止" in display_state(r, 9).status


def test_alarm_status_shows_target_time():
    r = rt(Kind.ALARM, target="07:30", repeat=True)
    assert display_state(r, 0).status.startswith("時刻指定 · 07:30 · 毎日")


def test_stopped_alarm_says_stopped():
    r = rt(Kind.ALARM, target="07:30")
    assert "停止中" in display_state(r, 0).status
