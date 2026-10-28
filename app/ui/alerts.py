"""終了時のお知らせ（音・Windows 通知・点滅）。ウィンドウはアクティブにしない。"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QSoundEffect

from . import theme

FLASH_SECONDS = 30
FLASH_INTERVAL_MS = 400
SOUND_LOOPS = 3
SOUND_NAMES = {"chime": "チャイム", "beep": "ブザー", "digital": "デジタル"}


class AlertManager(QObject):
    flash_toggled = Signal(bool)  # 点滅の点灯(True)/消灯(False)
    changed = Signal()

    def __init__(self, notify: Callable[[str, str], None], play_sound: bool = True, parent=None):
        super().__init__(parent)
        self._notify = notify
        self._play_sound = play_sound
        self.active: dict[str, float] = {}  # timer_id → 点滅を止める時刻
        self.sound_requests: list[str] = []  # 鳴らそうとした timer_id（テスト・確認用）
        self.sound_owner: str | None = None  # 今の音（1つだけ）を鳴らしたタイマー
        self.phase = True
        self._effect = QSoundEffect(self)
        self._sound_name = ""
        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(FLASH_INTERVAL_MS)
        self._flash_timer.timeout.connect(self._toggle_phase)

    def configure(self, sound_name: str, volume: float) -> None:
        if sound_name != self._sound_name:
            self._sound_name = sound_name
            self._effect.setSource(QUrl.fromLocalFile(str(theme.asset(f"sounds/{sound_name}.wav"))))
        self._effect.setVolume(volume)

    def is_active(self, timer_id: str) -> bool:
        return timer_id in self.active

    def alert(self, timer_id: str, title: str, message: str, sound: bool, now: float) -> None:
        # 同じタイマーの前のお知らせは打ち切って出し直す（別タイマーとは並存）
        self.active[timer_id] = now + FLASH_SECONDS
        if not sound and self.sound_owner == timer_id:
            self._stop_sound()
        if sound:
            self.sound_requests.append(timer_id)
            self.sound_owner = timer_id
            if self._play_sound:
                self._effect.stop()
                self._effect.setLoopCount(SOUND_LOOPS)
                self._effect.play()
        self._notify(title, message)
        self.phase = True
        if not self._flash_timer.isActive():
            self._flash_timer.start()
        self.changed.emit()

    def preview(self, sound_name: str, volume: float) -> None:
        self.configure(sound_name, volume)
        if self._play_sound:
            self._effect.stop()
            self._effect.setLoopCount(1)
            self._effect.play()

    def tick(self, now: float) -> None:
        expired = [tid for tid, until in self.active.items() if now >= until]
        for tid in expired:
            del self.active[tid]
        if expired:
            self._after_change()

    def dismiss(self, timer_id: str | None = None) -> None:
        if timer_id is None:
            self.active.clear()
        else:
            self.active.pop(timer_id, None)
        # 音は1つしかないので、今鳴っているのがそのタイマーの音のときだけ止める
        # （別のタイマーの点滅だけを止めたときに、後から鳴った音を止めない）
        if timer_id is None or timer_id == self.sound_owner:
            self._stop_sound()
        self._after_change()

    def _stop_sound(self) -> None:
        self._effect.stop()
        self.sound_owner = None

    def _after_change(self) -> None:
        if not self.active:
            self._flash_timer.stop()
            self.phase = True
        self.changed.emit()

    def _toggle_phase(self) -> None:
        self.phase = not self.phase
        self.flash_toggled.emit(self.phase)
