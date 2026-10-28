import json

from app.core.settings import DEFAULT_HOTKEYS, Settings
from app.core.store import Store
from app.core.timers import Kind, State, TimerRuntime, TimerSpec


def _sw(id_="a", name="作業"):
    return TimerRuntime(TimerSpec(id=id_, kind=Kind.STOPWATCH, name=name, color="green"))


def test_load_missing_returns_defaults(tmp_path):
    s, timers = Store(tmp_path).load()
    assert s == Settings() and timers == []
    assert s.hotkeys == DEFAULT_HOTKEYS


def test_roundtrip(tmp_path):
    t = _sw()
    t.start(0)
    t.lap(3)
    s = Settings(opacity=0.5, mini_mode=True, normal_rect=[10, 20, 400, 300])
    Store(tmp_path).save(s, [t], now=7)
    s2, timers = Store(tmp_path).load()
    assert s2.opacity == 0.5 and s2.mini_mode and s2.normal_rect == [10, 20, 400, 300]
    assert timers[0].spec.name == "作業" and timers[0].laps == [3]
    assert timers[0].state == State.PAUSED and timers[0].elapsed(100) == 7


def test_corrupt_json_moves_to_bak(tmp_path):
    (tmp_path / "state.json").write_text("{broken", encoding="utf-8")
    s, timers = Store(tmp_path).load()
    assert timers == [] and s == Settings()
    assert (tmp_path / "state.json.bak").read_text(encoding="utf-8") == "{broken"
    assert not (tmp_path / "state.json").exists()


def test_bad_timer_entry_is_skipped(tmp_path):
    good = _sw("g").to_dict(0)
    data = {"settings": {}, "timers": [{"spec": {"kind": "nope"}}, good]}
    (tmp_path / "state.json").write_text(json.dumps(data), encoding="utf-8")
    _, timers = Store(tmp_path).load()
    assert [t.spec.id for t in timers] == ["g"]


def test_timers_not_a_list_does_not_crash(tmp_path):
    (tmp_path / "state.json").write_text(json.dumps({"settings": {}, "timers": 5}), encoding="utf-8")
    _, timers = Store(tmp_path).load()
    assert timers == []


def test_invalid_timer_values_are_skipped(tmp_path):
    # 手で書き換えた等で duration 0 の繰り返しが入っていると、毎 tick ゼロ除算で全表示が止まる
    bad = TimerRuntime(TimerSpec(id="z", kind=Kind.COUNTDOWN, name="z", color="cyan",
                                 duration=0, repeat=True)).to_dict(0)
    data = {"settings": {}, "timers": [bad, _sw("g").to_dict(0)]}
    (tmp_path / "state.json").write_text(json.dumps(data), encoding="utf-8")
    _, timers = Store(tmp_path).load()
    assert [t.spec.id for t in timers] == ["g"]


def test_unknown_keys_ignored_and_opacity_clamped(tmp_path):
    data = {"settings": {"opacity": 0.01, "future_key": 1}, "timers": []}
    (tmp_path / "state.json").write_text(json.dumps(data), encoding="utf-8")
    s, _ = Store(tmp_path).load()
    assert s.opacity == 0.2


def test_missing_hotkey_actions_filled_with_defaults(tmp_path):
    data = {"settings": {"hotkeys": {"toggle": "Ctrl+Alt+Q"}}, "timers": []}
    (tmp_path / "state.json").write_text(json.dumps(data), encoding="utf-8")
    s, _ = Store(tmp_path).load()
    assert s.hotkeys["toggle"] == "Ctrl+Alt+Q"
    assert s.hotkeys["dismiss"] == DEFAULT_HOTKEYS["dismiss"]


def test_atomic_write_leaves_no_tmp(tmp_path):
    Store(tmp_path).save(Settings(), [_sw()], now=0)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["state.json"]


def test_save_creates_missing_dir(tmp_path):
    d = tmp_path / "nested" / "DigitalTimer"
    Store(d).save(Settings(), [], now=0)
    assert (d / "state.json").exists()


def test_default_hotkeys_not_shared_between_instances():
    a = Settings()
    a.hotkeys["toggle"] = "X"
    assert Settings().hotkeys["toggle"] == "Ctrl+Alt+S"


def test_single_mini_timer_migrates_to_list():
    assert Settings.from_dict({"mini_timer_id": "x"}).mini_timer_ids == ["x"]
    assert Settings.from_dict({"mini_timer_ids": "broken"}).mini_timer_ids == []
    assert Settings.from_dict({"mini_timer_ids": ["a", "b"]}).mini_timer_ids == ["a", "b"]
