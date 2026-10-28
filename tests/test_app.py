import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QFormLayout, QPushButton, QToolButton, QWidget

from app.controller import Controller
from app.core.settings import Settings
from app.core.store import Store
from app.core.timers import Kind, State, TimerSpec
from app.single_instance import acquire
from app.ui.dialogs import TimerEditDialog


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def make(qtbot, tmp_path):
    made = []

    def _make(store_dir=tmp_path):
        clock = FakeClock()
        notes = []
        c = Controller(store_dir, clock=clock, register_hotkeys=False, use_tray=False,
                       play_sound=False, notify=lambda title, msg: notes.append((title, msg)))
        c.timer.stop()  # テストでは tick を手で呼ぶ
        made.append(c)
        return c, clock, notes

    yield _make
    for c in made:
        c.shutdown()


def cd(seconds, repeat=False, id_="c1"):
    return TimerSpec(id=id_, kind=Kind.COUNTDOWN, name="カウント", color="cyan",
                     duration=seconds, repeat=repeat)


def test_add_countdown_and_finish_alerts_once(make):
    c, clock, notes = make()
    c.add_timer(cd(60))
    c.toggle("c1")
    clock.t += 61
    c.tick()
    c.tick()
    assert len(notes) == 1 and "カウント" in notes[0][0]
    assert c.alerts.is_active("c1")
    assert c.alerts.sound_requests == ["c1"]
    assert c.main.card("c1").digits._flash


def test_sound_off_timer_does_not_request_sound(make):
    c, clock, notes = make()
    spec = cd(10)
    spec.sound = False
    c.add_timer(spec)
    c.toggle("c1")
    clock.t += 11
    c.tick()
    assert len(notes) == 1 and c.alerts.sound_requests == []


def test_repeat_after_long_gap_alerts_once(make):
    c, clock, notes = make()
    c.add_timer(cd(10, repeat=True))
    c.toggle("c1")
    clock.t += 95
    c.tick()
    assert len(notes) == 1
    assert c.runtime("c1").state == State.RUNNING


def test_same_timer_realert_restarts_not_duplicates(make):
    c, clock, notes = make()
    c.add_timer(cd(10, repeat=True))
    c.toggle("c1")
    clock.t += 10
    c.tick()
    clock.t += 10
    c.tick()
    assert list(c.alerts.active) == ["c1"] and len(notes) == 2


def test_mini_frame_flashes_with_alert(make):
    c, clock, _ = make()
    c.add_timer(cd(5))
    c.toggle_mini()
    c.toggle("c1")
    clock.t += 6
    c.tick()
    assert c.mini.panel.outline is not None  # 点灯側
    c.alerts._toggle_phase()
    assert c.mini.panel.outline is None  # 消灯側
    c.dismiss_alerts()
    assert c.mini.panel.outline is None


def test_dismiss_stops_flash(make):
    c, clock, _ = make()
    c.add_timer(cd(5))
    c.toggle("c1")
    clock.t += 6
    c.tick()
    c.dismiss_alerts()
    c.refresh()
    assert not c.alerts.is_active("c1")
    assert not c.main.card("c1").digits._flash


def test_alert_expires_after_30_seconds(make):
    c, clock, _ = make()
    c.add_timer(cd(5))
    c.toggle("c1")
    clock.t += 6
    c.tick()
    clock.t += 31
    c.tick()
    assert not c.alerts.is_active("c1")


def test_running_timer_saved_periodically(make, tmp_path):
    # 強制終了・停電でも、動いていたタイマーの経過が最大30秒の遅れで残る
    c, clock, _ = make()
    c.add_timer(TimerSpec(id="s", kind=Kind.STOPWATCH, name="SW", color="cyan"))
    c.toggle("s")
    c.save()
    clock.t += 31
    c.tick()
    _, timers = Store(tmp_path).load()
    assert timers[0].elapsed(0) >= 31


def test_shutdown_survives_save_error(make):
    c, _, _ = make()

    def boom(*a, **k):
        raise PermissionError("locked by antivirus")

    c.store.save = boom
    c.shutdown()  # 例外で終了処理が止まらない
    assert not c.main.isVisible()


def test_opacity_applies_and_persists(make, tmp_path):
    c, _, _ = make()
    c.set_opacity(0.5)
    assert abs(c.main.windowOpacity() - 0.5) < 0.01
    c.shutdown()
    c2, _, _ = make()
    assert c2.settings.opacity == 0.5


def test_opacity_clamped(make):
    c, _, _ = make()
    c.set_opacity(0.05)
    assert c.settings.opacity == 0.2


def test_ctrl_wheel_changes_opacity(make, qtbot):
    c, _, _ = make()
    c.set_opacity(0.8)
    target = c.main.centralWidget()
    ev = QWheelEvent(QPointF(10, 10), QPointF(10, 10), QPoint(0, 0), QPoint(0, -120),
                     Qt.MouseButton.NoButton, Qt.KeyboardModifier.ControlModifier,
                     Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(target, ev)
    assert abs(c.settings.opacity - 0.75) < 1e-6


def test_mini_toggle_shows_mini_hides_main(make):
    c, _, _ = make()
    c.add_timer(cd(60))
    c.toggle_mini()
    assert c.mini.isVisible() and not c.main.isVisible()
    assert c.settings.mini_timer_id == "c1"
    c.toggle_mini()
    assert c.main.isVisible() and not c.mini.isVisible()


def test_hotkey_toggle_starts_selected(make):
    c, _, _ = make()
    c.add_timer(cd(60))
    c.on_hotkey("toggle")
    assert c.runtime("c1").state == State.RUNNING
    c.on_hotkey("toggle")
    assert c.runtime("c1").state == State.PAUSED


def test_hotkey_lap_on_stopwatch(make):
    c, clock, _ = make()
    c.add_timer(TimerSpec(id="s", kind=Kind.STOPWATCH, name="SW", color="cyan"))
    c.on_hotkey("toggle")
    clock.t += 3
    c.on_hotkey("lap")
    assert c.runtime("s").laps == [3]


def test_click_through_toggle(make):
    c, _, notes = make()
    c.toggle_click_through()
    assert c.click_through and c.main.windowFlags() & Qt.WindowType.WindowTransparentForInput
    assert notes  # 解除方法を通知で伝える
    c.toggle_click_through()
    assert not c.main.windowFlags() & Qt.WindowType.WindowTransparentForInput


def test_click_through_not_restored_on_restart(make):
    c, _, _ = make()
    c.toggle_click_through()
    c.shutdown()
    c2, _, _ = make()
    assert not c2.click_through


def test_remove_timer(make):
    c, _, _ = make()
    c.add_timer(cd(60))
    c.remove_timer("c1")
    assert c.runtimes == [] and c.main.card("c1") is None


def test_update_timer_changing_duration_resets(make):
    c, clock, _ = make()
    c.add_timer(cd(60))
    c.toggle("c1")
    clock.t += 5
    c.update_timer(cd(120))
    assert c.runtime("c1").state == State.IDLE and c.runtime("c1").remaining(clock()) == 120


def test_update_timer_renaming_keeps_running(make):
    c, _, _ = make()
    c.add_timer(cd(60))
    c.toggle("c1")
    spec = cd(60)
    spec.name = "新しい名前"
    c.update_timer(spec)
    assert c.runtime("c1").state == State.RUNNING and c.runtime("c1").spec.name == "新しい名前"


def test_offscreen_position_is_clamped(qtbot, tmp_path, make):
    Store(tmp_path).save(Settings(normal_rect=[90000, 90000, 420, 500]), [], now=0)
    c, _, _ = make()
    screen = QApplication.primaryScreen().availableGeometry()
    assert screen.intersects(c.main.geometry())


def test_alert_does_not_activate_window(make, qtbot):
    c, clock, _ = make()
    other = QWidget()
    qtbot.addWidget(other)
    other.show()
    other.activateWindow()
    qtbot.waitUntil(lambda: QApplication.activeWindow() is other, timeout=3000)
    c.add_timer(cd(5))
    c.toggle("c1")
    clock.t += 6
    c.tick()
    qtbot.wait(100)
    assert QApplication.activeWindow() is other


def _glass_rect(panel):
    """パネル画像のガラス面（上の暗い溝より下、下の光る縁より上）を実測する。"""
    img = panel.grab().toImage()
    x = img.width() // 2
    lum = [max(img.pixelColor(x, y).getRgb()[:3]) for y in range(img.height())]
    groove = next(y for y in range(img.height()) if lum[y] < 15)
    top = next(y for y in range(groove, img.height()) if lum[y] >= 15)
    bottom = next(y for y in range(img.height() // 2, img.height()) if lum[y] > 90) - 1
    return top, bottom


@pytest.mark.parametrize("size", [(320, 124), (240, 116), (480, 170)])
def test_mini_text_stays_inside_glass(make, size):
    # 名前・状態の文字と進捗バーが金属の縁にかからないこと
    c, _, _ = make()
    c.add_timer(cd(60))
    c.mini.resize(*size)
    c.mini.show()
    QApplication.processEvents()
    top, bottom = _glass_rect(c.mini.panel)
    for w in (c.mini.name, c.mini.status, c.mini.digits):
        assert w.geometry().top() >= top, w
    assert c.mini.progress.geometry().bottom() <= bottom


def test_dialogs_stay_above_on_top_window(make):
    # 最前面のウィンドウの後ろにダイアログが隠れないこと（実機スクショで発覚）
    c, _, _ = make()
    d = c.prepare_dialog(TimerEditDialog())
    assert d.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    c.set_always_on_top(False)
    d2 = c.prepare_dialog(TimerEditDialog())
    assert not d2.windowFlags() & Qt.WindowType.WindowStaysOnTopHint


def test_dialog_ok_disabled_for_zero_duration(qtbot):
    d = TimerEditDialog()
    qtbot.addWidget(d)
    d.set_kind(Kind.COUNTDOWN)
    d.cd_h.setValue(0)
    d.cd_m.setValue(0)
    d.cd_s.setValue(0)
    ok = d.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok.isEnabled() and d.error.text()
    d.cd_s.setValue(30)
    assert ok.isEnabled()
    assert d.get_spec().duration == 30


def test_dialog_pomodoro_spec(qtbot):
    d = TimerEditDialog()
    qtbot.addWidget(d)
    d.set_kind(Kind.POMODORO)
    d.po_work.setValue(50)
    d.po_rest.setValue(10)
    d.po_sets.setValue(3)
    s = d.get_spec()
    assert (s.kind, s.work, s.rest, s.sets) == (Kind.POMODORO, 3000, 600, 3)


def test_dialog_name_is_first_and_focused(qtbot):
    # 何のタイマーか分かる名前を付けやすいよう、名前欄を先頭に置いて最初から入力できるようにする
    d = TimerEditDialog()
    qtbot.addWidget(d)
    d.show()
    qtbot.waitExposed(d)
    assert d.focusWidget() is d.name
    item = d.form.itemAt(0, QFormLayout.ItemRole.FieldRole)
    assert item is not None and item.widget() is d.name
    assert d.name.text() == "" and "例" in d.name.placeholderText()


def test_dialog_name_used_or_falls_back_to_kind(qtbot):
    d = TimerEditDialog()
    qtbot.addWidget(d)
    d.set_kind(Kind.POMODORO)
    assert d.get_spec().name == "ポモドーロ"  # 空欄なら種類の名前
    d.name.setText("  英語の勉強 ")
    d.set_kind(Kind.COUNTDOWN)
    assert d.get_spec().name == "英語の勉強"
    assert d.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()


def test_dialog_edit_prefills(qtbot):
    d = TimerEditDialog(cd(3725, repeat=True))
    qtbot.addWidget(d)
    assert (d.cd_h.value(), d.cd_m.value(), d.cd_s.value()) == (1, 2, 5)
    assert d.cd_repeat.isChecked() and d.get_spec().id == "c1"


def test_single_instance(qtbot):
    name = "DigitalTimerTest-single"
    server = acquire(name)
    assert server is not None
    got = []
    server.show_requested.connect(lambda: got.append(1))
    assert acquire(name) is None
    qtbot.waitUntil(lambda: got == [1], timeout=3000)
    server.close()


# ---- 時刻指定 ----
def alarm(target="17:00", repeat=False):
    return TimerSpec(id="a1", kind=Kind.ALARM, name="会議", color="cyan", target=target, repeat=repeat)


@pytest.fixture
def wall(monkeypatch):
    from datetime import datetime

    from app.core.timers import TimerRuntime
    box = {"t": datetime(2026, 10, 29, 16, 0)}
    monkeypatch.setattr(TimerRuntime, "wall_clock", staticmethod(lambda: box["t"]))
    return box


def advance(clock, wall, seconds):
    from datetime import timedelta
    clock.t += seconds
    wall["t"] += timedelta(seconds=seconds)


def test_alarm_starts_on_add_and_alerts_at_time(make, wall):
    c, clock, notes = make()
    c.add_timer(alarm())
    r = c.runtime("a1")
    assert r.state == State.RUNNING and r.remaining(clock()) == 3600
    advance(clock, wall, 3600)
    c.tick()
    assert notes and "会議" in notes[0][0] and "17:00 になりました" in notes[0][1]
    assert r.state == State.FINISHED


def test_daily_alarm_message_names_time(make, wall):
    c, clock, notes = make()
    c.add_timer(alarm(repeat=True))
    advance(clock, wall, 3600)
    c.tick()
    assert "17:00 になりました" in notes[0][1]


def test_toggle_while_alerting_only_silences(make, wall):
    # 鳴っている最中のスタート/一時停止は「止める」だけ。毎日の時刻指定が止まったり、
    # 1回だけの時刻指定が翌日にまた動き出したりしない
    c, clock, _ = make()
    c.add_timer(alarm(repeat=True))
    advance(clock, wall, 3600)
    c.tick()
    c.toggle("a1")
    assert not c.alerts.is_active("a1") and c.runtime("a1").state == State.RUNNING
    c.update_timer(alarm())
    advance(clock, wall, 86400)
    c.tick()
    c.toggle("a1")
    assert not c.alerts.is_active("a1") and c.runtime("a1").state == State.FINISHED


def test_alarm_missed_while_closed_is_reported(make, wall, tmp_path):
    c, clock, _ = make()
    c.add_timer(alarm())
    c.save()
    wall["t"] = wall["t"].replace(hour=18)  # 閉じている間に 17:00 を過ぎた
    c2, _, notes = make()
    c2.tick()
    assert notes and "17:00 を過ぎていました" in notes[0][1]
    assert c2.runtime("a1").state == State.FINISHED


def test_alarm_rearmed_after_restart(make, wall, tmp_path):
    c, clock, _ = make()
    c.add_timer(alarm())
    c.save()
    c2, clock2, _ = make()
    r = c2.runtime("a1")
    assert r.state == State.RUNNING and r.remaining(clock2()) == 3600


def test_alarm_target_change_restarts(make, wall):
    c, clock, _ = make()
    c.add_timer(alarm())
    c.update_timer(alarm("18:30"))
    r = c.runtime("a1")
    assert r.state == State.RUNNING and r.remaining(clock()) == 9000


def test_dialog_alarm_spec(qtbot):
    from PySide6.QtCore import QTime
    d = TimerEditDialog()
    qtbot.addWidget(d)
    d.set_kind(Kind.ALARM)
    d.al_time.setTime(QTime(7, 30))
    d.al_repeat.setChecked(True)
    s = d.get_spec()
    assert (s.kind, s.target, s.repeat) == (Kind.ALARM, "07:30", True)
    assert d.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    d2 = TimerEditDialog(s)
    qtbot.addWidget(d2)
    assert d2.al_time.time() == QTime(7, 30) and d2.al_repeat.isChecked()
    assert d2.stack.currentWidget() is d2.al_page


# ---- 軽微な点 ----
def test_mini_long_name_is_elided_and_status_kept(make):
    c, _, _ = make()
    spec = cd(60)
    spec.name = "とても長い名前のタイマーで何のためのものか全部書いてある"
    c.add_timer(spec)
    c.toggle("c1")
    c.toggle("c1")  # 一時停止中
    c.mini.resize(240, 116)
    c.mini.show()
    QApplication.processEvents()
    status = c.mini.status
    assert status.width() >= status.fontMetrics().horizontalAdvance(status.text())
    shown = c.mini.name.shown_text()
    assert shown.endswith("…") and c.mini.name.fontMetrics().horizontalAdvance(shown) <= c.mini.name.width()


def test_dialog_keeps_long_name(qtbot):
    spec = cd(60)
    spec.name = "名" * 60
    d = TimerEditDialog(spec)
    qtbot.addWidget(d)
    assert d.get_spec().name == "名" * 60


def test_finished_alarm_restarts_when_saved(make, wall):
    # 鳴り終わった時刻指定は、「毎日」だけ変えて保存しても動き始める（保存したら動く、の約束どおり）
    c, clock, _ = make()
    c.add_timer(alarm())
    advance(clock, wall, 3600)
    c.tick()
    c.update_timer(alarm(repeat=True))
    r = c.runtime("a1")
    assert r.state == State.RUNNING and r.remaining(clock()) == 86400
    assert not c.alerts.is_active("a1")


def test_dismiss_one_alert_keeps_other_sound(make):
    # 音は1つ（最後に鳴ったタイマーのもの）。止めたのがそのタイマーのときだけ音を止める
    c, clock, _ = make()
    c.add_timer(cd(5))
    c.add_timer(cd(15, id_="c2"))
    c.toggle("c1")
    c.toggle("c2")
    clock.t += 6
    c.tick()
    assert c.alerts.sound_owner == "c1"
    clock.t += 10
    c.tick()  # c1 の点滅中に c2 が鳴る → 今の音は c2 のもの
    assert c.alerts.sound_owner == "c2"
    c.alerts.dismiss("c1")
    assert c.alerts.sound_owner == "c2"  # c2 の音は止めない
    c.alerts.dismiss("c2")
    assert c.alerts.sound_owner is None


def test_silent_realert_releases_sound(make):
    c, clock, _ = make()
    c.alerts.alert("x", "t", "m", sound=True, now=0)
    c.alerts.alert("x", "t", "m", sound=False, now=1)
    assert c.alerts.sound_owner is None


def test_card_long_name_keeps_buttons_visible(make):
    c, _, _ = make()
    spec = cd(60)
    spec.name = "あ" * 120
    c.add_timer(spec)
    c.main.resize(440, 540)
    c.main.show()
    QApplication.processEvents()
    card = c.main.card("c1")
    assert card.name.shown_text().endswith("…")
    for b in card.findChildren(QToolButton):
        assert b.isVisible() and b.mapTo(card, b.rect().topRight()).x() <= card.width()


def test_click_through_notice_when_hotkey_unavailable(make):
    c, _, notes = make()
    c.hotkey_failures = ["clickthrough"]
    c.toggle_click_through()
    title, msg = notes[-1]
    assert "トレイ" in msg and c.settings.hotkeys["clickthrough"] not in msg
    c.toggle_click_through()


def test_settings_dialog_pauses_global_hotkeys(make, monkeypatch):
    # 設定画面でキーを押したとき、登録済みのショートカットが動かず、入力欄に記録されるようにする
    from app.ui.dialogs import SettingsDialog
    c, _, _ = make()
    calls = []

    class FakeHotkeys:
        def unregister_all(self):
            calls.append("off")

        def register_all(self, mapping):
            calls.append("on")
            return []

    c.hotkeys = FakeHotkeys()  # type: ignore[assignment]
    monkeypatch.setattr(SettingsDialog, "exec", lambda self: calls.append("dialog") or 0)
    c.open_settings()
    assert calls == ["off", "dialog", "on"]
    c.hotkeys = None


# ---- ミニ表示に複数のタイマー ----
def three(c):
    for i in (1, 2, 3):
        c.add_timer(cd(60, id_=f"c{i}"))


def test_mini_shows_all_checked_timers(make):
    c, _, _ = make()
    three(c)
    c.set_mini_shown("c3", True)
    c.set_mini_shown("c1", True)
    c.toggle_mini()
    QApplication.processEvents()
    assert c.mini.timer_ids() == ["c1", "c3"]  # 並びは通常表示と同じ
    per = c.mini.height() // 2
    c.set_mini_shown("c2", True)
    assert c.mini.timer_ids() == ["c1", "c2", "c3"] and c.mini.height() == per * 3
    c.set_mini_shown("c1", False)
    assert c.mini.timer_ids() == ["c2", "c3"] and c.mini.height() == per * 2


def test_card_checkbox_toggles_mini(make):
    c, _, _ = make()
    three(c)
    c.main.card("c2").mini_check.setChecked(True)
    assert c.settings.mini_timer_ids == ["c2"]
    c.set_mini_shown("c3", True)
    assert c.main.card("c3").mini_check.isChecked()
    c.main.card("c2").mini_check.setChecked(False)
    assert c.settings.mini_timer_ids == ["c3"]


def test_removed_timer_leaves_mini(make):
    c, _, _ = make()
    three(c)
    c.set_mini_shown("c1", True)
    c.set_mini_shown("c2", True)
    c.remove_timer("c1")
    assert c.settings.mini_timer_ids == ["c2"] and c.mini.timer_ids() == ["c2"]


def test_mini_focused_panel_gets_hotkeys(make):
    c, _, _ = make()
    three(c)
    c.set_mini_shown("c1", True)
    c.set_mini_shown("c3", True)
    c.toggle_mini()
    QApplication.processEvents()
    second = c.mini.panels[1]
    assert c.mini.panel_at(second.geometry().center()) is second
    c.focus_mini("c3")
    c.on_hotkey("toggle")
    assert c.runtime("c3").state == State.RUNNING and c.runtime("c1").state == State.IDLE


def test_mini_flashes_only_alerting_panel(make):
    c, clock, _ = make()
    c.add_timer(cd(5))
    c.add_timer(cd(60, id_="c2"))
    c.set_mini_shown("c1", True)
    c.set_mini_shown("c2", True)
    c.toggle_mini()
    c.toggle("c1")
    clock.t += 6
    c.tick()
    p1, p2 = c.mini.panels
    assert p1.outline is not None and p2.outline is None


def test_mini_with_nothing_checked_shows_selected(make):
    c, _, _ = make()
    three(c)
    c.select("c2")
    c.toggle_mini()
    assert c.mini.timer_ids() == ["c2"] and c.settings.mini_timer_ids == ["c2"]


def test_mini_height_kept_after_restart(make):
    c, _, _ = make()
    three(c)
    c.set_mini_shown("c1", True)
    c.set_mini_shown("c2", True)
    c.toggle_mini()
    h = c.mini.height()
    c.save()
    c2, _, _ = make()
    assert c2.mini.timer_ids() == ["c1", "c2"] and c2.mini.height() == h


def test_mini_height_saved_even_while_hidden(make):
    # 通常表示のまま枚数を変えても、保存する窓の高さが今の枚数に合う
    c, _, _ = make()
    three(c)
    for t in ("c1", "c2", "c3"):
        c.set_mini_shown(t, True)
    per = c.mini.height() // 3
    c.settings.mini_rect = None  # ほかの窓の移動などで保存されることに頼らない
    c.set_mini_shown("c2", False)
    c.set_mini_shown("c3", False)
    assert c.settings.mini_rect is not None and c.settings.mini_rect[3] == per


def test_mini_grows_but_stays_on_screen(make):
    c, _, _ = make()
    for i in range(12):
        c.add_timer(cd(60, id_=f"t{i}"))
    area = QApplication.primaryScreen().availableGeometry()
    c.toggle_mini()
    c.mini.move(c.mini.x(), area.bottom() - c.mini.height())
    for i in range(12):
        c.set_mini_shown(f"t{i}", True)
    g = c.mini.geometry()
    assert area.contains(g), (g, area)


def test_card_header_leaves_room_for_name(make):
    c, _, _ = make()
    spec = cd(60)
    spec.name = "英語の勉強"
    c.add_timer(spec)
    c.toggle("c1")
    c.toggle("c1")
    c.main.resize(440, 540)
    c.main.show()
    QApplication.processEvents()
    card = c.main.card("c1")
    assert card.name.shown_text() == "英語の勉強"


def test_deleted_ids_dropped_on_load(make, tmp_path):
    Store(tmp_path).save(Settings(mini_timer_ids=["gone"]), [], now=0)
    c, _, _ = make()
    c.add_timer(cd(60))
    c.toggle_mini()
    assert c.settings.mini_timer_ids == ["c1"]


def test_stopwatch_card_buttons_not_clipped(make):
    from app.ui import theme
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    app.setStyleSheet(theme.stylesheet())  # 実際のアプリと同じ見た目の大きさで測る
    c, _, _ = make()
    c.add_timer(TimerSpec(id="s", kind=Kind.STOPWATCH, name="SW", color="cyan"))
    c.toggle("s")  # 動いている間は「❚❚ 一時停止」で、「▶ スタート」より幅が広い
    c.main.resize(440, 540)
    c.main.show()
    QApplication.processEvents()
    card = c.main.card("s")
    for b in card.findChildren(QPushButton):
        if b.isVisible():
            assert b.width() >= b.sizeHint().width(), b.text()
    app.setStyleSheet("")
