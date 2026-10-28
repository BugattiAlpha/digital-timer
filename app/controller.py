"""アプリ全体のまとめ役。タイマー・設定・ウィンドウ・お知らせ・ショートカットをつなぐ。"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, TypeVar

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QWidget

from .core.settings import clamp_opacity
from .core.store import Store
from .core.timers import Event, Kind, State, TimerRuntime, TimerSpec
from .ui.alerts import AlertManager
from .ui.dialogs import SettingsDialog, TimerEditDialog
from .ui.display import display_state
from .ui.main_window import MainWindow
from .ui.mini_window import MiniWindow
from .win32.window import set_click_through

log = logging.getLogger(__name__)

TICK_MS = 100
SAVE_DELAY_MS = 500
PERIODIC_SAVE_SECONDS = 30  # 動いている間の定期保存（強制終了・停電で失う時間の上限）
WHEEL_STEP = 0.05
D = TypeVar("D", bound=QDialog)
_TIMING_FIELDS = ("kind", "duration", "work", "rest", "sets", "target")


class Controller(QObject):
    def __init__(self, store_dir: Path, clock: Callable[[], float] = time.monotonic,
                 register_hotkeys: bool = True, use_tray: bool = True, play_sound: bool = True,
                 notify: Callable[[str, str], None] | None = None):
        super().__init__()
        self.clock = clock
        self.store = Store(store_dir)
        self.settings, self.runtimes = self.store.load()
        for r in self.runtimes:
            if r.rearm:  # 動いていた時刻指定は同じ時刻のまま再開。閉じている間に過ぎていれば最初の tick で知らせる
                r.resume(clock())
        self._last_save = clock()
        self.click_through = False  # 保存しない（起動直後は必ず操作できる状態）
        self.hidden = False
        self.hotkey_failures: list[str] = []
        self._hotkeys_paused = False  # 設定画面を開いている間はショートカットを外している

        self.tray = None
        if use_tray:
            from .ui.tray import Tray
            self.tray = Tray(self)
            self.tray.show()
        if notify is None:
            notify = self.tray.notify if self.tray else (lambda title, msg: None)
        self.alerts = AlertManager(notify, play_sound=play_sound, parent=self)
        self.alerts.configure(self.settings.sound_name, self.settings.volume)
        self.alerts.flash_toggled.connect(lambda _phase: self.refresh())
        self.alerts.changed.connect(self.refresh)

        self.main = MainWindow(self)
        self.mini = MiniWindow(self)
        # 消したタイマーの id が残っていたら外す
        self.settings.mini_timer_ids = [t for t in self.settings.mini_timer_ids if self._find(t)]
        self.mini.set_timers(self.mini_ids())  # 保存した窓の高さは、パネルを並べた後の高さ
        self.main.restore_geometry(self.settings.normal_rect, MainWindow.default_rect())
        self.mini.restore_geometry(self.settings.mini_rect, MiniWindow.default_rect())
        self.main.geometry_changed.connect(self._on_geometry)
        self.mini.geometry_changed.connect(self._on_geometry)
        self.main.rebuild()

        self.hotkeys = None
        if register_hotkeys:
            from .win32.hotkeys import HotkeyManager
            self.hotkeys = HotkeyManager(self)
            self.hotkeys.triggered.connect(self.on_hotkey)
            self.hotkey_failures = self.hotkeys.register_all(self.settings.hotkeys)

        app = QApplication.instance()
        assert app is not None, "QApplication を先に作ってください"
        app.installEventFilter(self)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(SAVE_DELAY_MS)
        self._save_timer.timeout.connect(self.save)
        self.timer = QTimer(self)
        self.timer.setInterval(TICK_MS)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

        self._apply_window_settings()
        self.show_current()
        self.refresh()

    # ---- 参照 ----
    def runtime(self, timer_id: str) -> TimerRuntime:
        return next(r for r in self.runtimes if r.spec.id == timer_id)

    def _find(self, timer_id: str | None) -> TimerRuntime | None:
        return next((r for r in self.runtimes if r.spec.id == timer_id), None)

    def selected_id(self) -> str | None:
        """ショートカットの対象。ミニ表示中はミニでクリックしたもの、通常は最後に選んだもの。"""
        if self.settings.mini_mode:
            shown = self.mini_ids()
            if shown:
                return self.settings.mini_timer_id if self.settings.mini_timer_id in shown else shown[0]
        for tid in (self.settings.selected_timer_id,):
            if self._find(tid):
                return tid
        return self.runtimes[0].spec.id if self.runtimes else None

    def mini_ids(self) -> list[str]:
        """ミニ表示に出すタイマー（通常表示と同じ並び）。1つもチェックが無ければ選んでいるもの1つ。"""
        checked = set(self.settings.mini_timer_ids)
        ids = [r.spec.id for r in self.runtimes if r.spec.id in checked]
        if ids:
            return ids
        fallback = self.settings.selected_timer_id if self._find(self.settings.selected_timer_id) else None
        if fallback is None and self.runtimes:
            fallback = self.runtimes[0].spec.id
        return [fallback] if fallback else []

    # ---- 時間の進行 ----
    def tick(self) -> None:
        now = self.clock()
        fired = False
        for r in list(self.runtimes):
            for e in r.tick(now):
                self._on_event(r, e, now)
                fired = True
        self.alerts.tick(now)
        if fired:
            self.schedule_save()
        elif (now - self._last_save >= PERIODIC_SAVE_SECONDS
              and any(r.state == State.RUNNING for r in self.runtimes)):
            self.save()
        self.refresh()

    def _on_event(self, r: TimerRuntime, e: Event, now: float) -> None:
        if r.spec.kind == Kind.ALARM:
            if e.late > 60:
                message = f"{r.spec.target} を過ぎていました（アプリが動いていない間）"
            else:
                message = f"{r.spec.target} になりました"
        elif e.type == "phase":
            message = "休憩の時間です" if e.phase and e.phase.value == "break" else "作業を再開しましょう"
        elif e.type == "repeat":
            message = f"時間になりました（{r.cycles}回目）"
        elif r.spec.kind == Kind.POMODORO:
            message = "すべてのセットが終わりました"
        elif r.spec.kind == Kind.ALARM:
            message = f"{r.spec.target} になりました"
        else:
            message = "時間になりました"
        self.alerts.alert(r.spec.id, f"⏰ {r.spec.name}", message, sound=r.spec.sound, now=now)

    def refresh(self) -> None:
        now = self.clock()
        selected = self.selected_id()
        for r in self.runtimes:
            card = self.main.card(r.spec.id)
            if card is not None:
                card.refresh(display_state(r, now), r.spec.id == selected,
                             self.alerts.is_active(r.spec.id), self.alerts.phase)
        shown = self.mini_ids()
        self.mini.set_timers(list(shown))
        many = len(shown) > 1
        for p in self.mini.panels:
            r = self._find(p.timer_id)
            if r is None:
                p.refresh("", None, False, True, False)
            else:
                p.refresh(r.spec.name, display_state(r, now), self.alerts.is_active(r.spec.id),
                          self.alerts.phase, many and r.spec.id == selected)

    # ---- タイマー操作 ----
    def toggle(self, timer_id: str) -> None:
        if self.alerts.is_active(timer_id):
            # 鳴っている最中は止めるだけ（繰り返しのタイマーを一時停止したり、
            # 終わったタイマーをもう一度始めたりしない）
            self.alerts.dismiss(timer_id)
            self._changed()
            return
        r = self.runtime(timer_id)
        now = self.clock()
        if r.state == State.RUNNING:
            r.pause(now)
        else:
            r.start(now)
        self._changed()

    def reset(self, timer_id: str) -> None:
        self.runtime(timer_id).reset()
        if self.alerts.is_active(timer_id):
            self.alerts.dismiss(timer_id)
        self._changed()

    def lap(self, timer_id: str) -> None:
        self.runtime(timer_id).lap(self.clock())
        self._changed()

    def skip(self, timer_id: str) -> None:
        self.runtime(timer_id).skip(self.clock())
        self._changed()

    def select(self, timer_id: str) -> None:
        self.settings.selected_timer_id = timer_id
        self._changed()

    def focus_mini(self, timer_id: str) -> None:
        """ミニ表示でクリックしたタイマーに、ショートカットが効くようにする。"""
        self.settings.mini_timer_id = timer_id
        self._changed()

    def set_mini_shown(self, timer_id: str, on: bool) -> None:
        """ミニ表示に出す/出さないを切り替える（カードの「ミニ」とミニ表示の右クリックメニュー）。"""
        ids = [t for t in self.settings.mini_timer_ids if t != timer_id and self._find(t)]
        if on:
            ids.append(timer_id)
        self.settings.mini_timer_ids = ids
        self._changed()

    def _arm_if_alarm(self, r: TimerRuntime) -> None:
        # 時刻指定は「その時刻に鳴らす」設定なので、保存したらすぐ動かす
        if r.spec.kind == Kind.ALARM:
            r.start(self.clock())

    def add_timer(self, spec: TimerSpec) -> None:
        r = TimerRuntime(spec)
        self._arm_if_alarm(r)
        self.runtimes.append(r)
        self.settings.selected_timer_id = spec.id
        self.main.rebuild()
        self._changed()

    def update_timer(self, spec: TimerSpec) -> None:
        r = self.runtime(spec.id)
        timing_changed = any(getattr(r.spec, f) != getattr(spec, f) for f in _TIMING_FIELDS)
        if timing_changed:
            new = TimerRuntime(spec)
            self._arm_if_alarm(new)
            self.runtimes[self.runtimes.index(r)] = new
            self.alerts.dismiss(spec.id)
        else:
            r.spec = spec
            if spec.kind == Kind.ALARM and r.state in (State.IDLE, State.FINISHED):
                # 時刻指定は保存したら動く。止まっている/鳴り終わったものは、名前や「毎日」だけの変更でも動かす
                r.start(self.clock())
                if self.alerts.is_active(spec.id):
                    self.alerts.dismiss(spec.id)
        self.main.rebuild()
        self._changed()

    def remove_timer(self, timer_id: str) -> None:
        self.runtimes = [r for r in self.runtimes if r.spec.id != timer_id]
        self.settings.mini_timer_ids = [t for t in self.settings.mini_timer_ids if t != timer_id]
        if self.alerts.is_active(timer_id):
            self.alerts.dismiss(timer_id)
        self.main.rebuild()
        self._changed()

    def _changed(self) -> None:
        self.schedule_save()
        self.refresh()

    # ---- ショートカット ----
    def on_hotkey(self, action: str) -> None:
        tid = self.selected_id()
        per_timer = {"toggle": self.toggle, "reset": self.reset, "lap": self.lap}
        if action in per_timer:
            if tid:
                per_timer[action](tid)
            return
        {"mini": self.toggle_mini, "clickthrough": self.toggle_click_through,
         "show": self.toggle_visible, "dismiss": self.dismiss_alerts}[action]()

    def apply_hotkeys(self, mapping: dict[str, str]) -> list[str]:
        """保存して、登録できるか確かめる（設定画面を開いている間は、確かめた後また外す）。"""
        self.settings.hotkeys = dict(mapping)
        self.hotkey_failures = self.hotkeys.register_all(mapping) if self.hotkeys else []
        if self.hotkeys and self._hotkeys_paused:
            self.hotkeys.unregister_all()
        self.schedule_save()
        return self.hotkey_failures

    # ---- 表示 ----
    def windows(self) -> tuple[MainWindow, MiniWindow]:
        return self.main, self.mini

    def _apply_window_settings(self) -> None:
        for w in self.windows():
            w.setWindowOpacity(self.settings.opacity)
            w.apply_flags(self.settings.always_on_top, self.click_through)

    def show_current(self) -> None:
        if self.hidden:
            return
        show, hide = (self.mini, self.main) if self.settings.mini_mode else (self.main, self.mini)
        hide.hide()
        show.show()

    def show_window(self) -> None:
        """2つ目の起動から呼ばれる。ユーザー操作なので前面に出してよい。"""
        self.hidden = False
        self.show_current()
        w = self.mini if self.settings.mini_mode else self.main
        w.raise_()
        w.activateWindow()

    def toggle_visible(self) -> None:
        self.hidden = not self.hidden
        if self.hidden:
            for w in self.windows():
                w.hide()
        else:
            self.show_current()

    def toggle_mini(self) -> None:
        self.settings.mini_mode = not self.settings.mini_mode
        if self.settings.mini_mode:
            if not self.settings.mini_timer_ids:
                # 何もチェックしていなければ、今出すもの（選んでいるタイマー）にチェックを付ける
                self.settings.mini_timer_ids = self.mini_ids()
            if self.settings.mini_timer_id not in self.mini_ids():
                self.settings.mini_timer_id = self.selected_id()
        self.hidden = False
        self.show_current()
        self._changed()

    def set_opacity(self, value: float) -> None:
        self.settings.opacity = clamp_opacity(round(value, 2))
        for w in self.windows():
            w.setWindowOpacity(self.settings.opacity)
        self.schedule_save()

    def set_always_on_top(self, on: bool) -> None:
        self.settings.always_on_top = on
        self._apply_window_settings()
        self.schedule_save()

    def toggle_click_through(self) -> None:
        self.click_through = not self.click_through
        for w in self.windows():
            set_click_through(w, self.click_through)
        if self.click_through:
            keys = self.settings.hotkeys.get("clickthrough", "")
            if keys and "clickthrough" not in self.hotkey_failures:
                how = f"解除は {keys} か、トレイアイコンの右クリックメニューから"
            else:  # ショートカットが使えない（未設定・他アプリと衝突）ときは案内しない
                how = "解除はトレイアイコンの右クリックメニューから"
            self.alerts._notify("クリック透過 ON", how)

    def set_sound(self, name: str, volume: float) -> None:
        self.settings.sound_name = name
        self.settings.volume = volume
        self.alerts.configure(name, volume)
        self.schedule_save()

    def dismiss_alerts(self) -> None:
        self.alerts.dismiss()

    # ---- ダイアログ ----
    def prepare_dialog(self, dlg: D) -> D:
        """最前面のウィンドウの後ろに隠れないよう、ダイアログも最前面にそろえる。"""
        dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.settings.always_on_top)
        return dlg

    def _dialog_parent(self) -> QWidget | None:
        return self.main if self.main.isVisible() else None

    def edit_timer_dialog(self, timer_id: str | None = None) -> None:
        r = self._find(timer_id)
        dlg = self.prepare_dialog(TimerEditDialog(r.spec if r else None, self._dialog_parent()))
        if dlg.exec():
            spec = dlg.get_spec()
            if r:
                self.update_timer(spec)
            else:
                self.add_timer(spec)

    def open_settings(self) -> None:
        # 開いている間はショートカットを外す。外さないと、登録済みのキーを入力欄で押したとき
        # 記録されずにショートカットが動いてしまう
        if self.hotkeys:
            self.hotkeys.unregister_all()
            self._hotkeys_paused = True
        try:
            self.prepare_dialog(SettingsDialog(self, self._dialog_parent())).exec()
        finally:
            self._hotkeys_paused = False
            if self.hotkeys:
                self.hotkey_failures = self.hotkeys.register_all(self.settings.hotkeys)

    def confirm(self, title: str, text: str) -> bool:
        box = QMessageBox(QMessageBox.Icon.Question, title, text,
                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                          self._dialog_parent())
        return self.prepare_dialog(box).exec() == QMessageBox.StandardButton.Yes

    # ---- 保存・終了 ----
    def _on_geometry(self) -> None:
        self.settings.normal_rect = self.main.rect_list()
        self.settings.mini_rect = self.mini.rect_list()
        self.schedule_save()

    def schedule_save(self) -> None:
        self._save_timer.start()

    def save(self) -> None:
        self._last_save = self.clock()
        self.store.save(self.settings, self.runtimes, self._last_save)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        # Ctrl+ホイールで透明度を変える（カードの上でもスクロールより優先）
        if (isinstance(event, QWheelEvent) and isinstance(obj, QWidget)
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier
                and obj.window() in self.windows()):
            step = WHEEL_STEP if event.angleDelta().y() > 0 else -WHEEL_STEP
            self.set_opacity(self.settings.opacity + step)
            return True
        return False

    def shutdown(self) -> None:
        self.timer.stop()
        self._save_timer.stop()
        # 点滅タイマーが削除済みのカードを触らないよう、先にお知らせを止めて切り離す
        self.alerts.dismiss()
        self.alerts.blockSignals(True)
        try:
            self.save()
        except OSError as e:
            # ウイルス対策ソフトがファイルを掴んでいる等で保存できなくても、終了は止めない
            log.warning("終了時の保存に失敗しました: %s", e)
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        if self.hotkeys:
            self.hotkeys.unregister_all()
        if self.tray:
            self.tray.hide()
        for w in self.windows():
            w.hide()
            w.deleteLater()

    def quit(self) -> None:
        self.shutdown()
        QApplication.quit()
