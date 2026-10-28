"""Windows のグローバルショートカット（RegisterHotKey）。

他のアプリを操作中でも押せるキー。受け口として表示しない専用ウィジェットを1つ持ち、
その nativeEvent で WM_HOTKEY を受け取る。
"""
from __future__ import annotations

import ctypes
import itertools
from ctypes import wintypes

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
_MODS = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT,
         "shift": MOD_SHIFT, "win": MOD_WIN, "meta": MOD_WIN}

_user32 = ctypes.windll.user32
_user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
_user32.RegisterHotKey.restype = wintypes.BOOL
_user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.UnregisterHotKey.restype = wintypes.BOOL

# プロセス内で一意な ID（0x0000〜0xBFFF がアプリ用）
_ids = itertools.count(1)


def _vk(key: str) -> int:
    k = key.upper()
    if len(k) == 1 and (k.isascii() and (k.isalpha() or k.isdigit())):
        return ord(k)
    if k.startswith("F") and k[1:].isdigit() and 1 <= int(k[1:]) <= 24:
        return 0x70 + int(k[1:]) - 1
    raise ValueError(f"使えないキーです: {key}")


def parse_hotkey(text: str) -> tuple[int, int]:
    """'Ctrl+Alt+S' → (修飾キー, 仮想キーコード)。修飾キーなしは不可。"""
    parts = [p.strip() for p in text.split("+")]
    if not text or any(not p for p in parts):
        raise ValueError(f"ショートカットの形式が不正です: {text!r}")
    mods, keys = 0, []
    for p in parts:
        if p.lower() in _MODS:
            mods |= _MODS[p.lower()]
        else:
            keys.append(p)
    if len(keys) != 1 or not mods:
        raise ValueError(f"修飾キー＋キー1つで指定してください: {text!r}")
    return mods | MOD_NOREPEAT, _vk(keys[0])


class _Receiver(QWidget):
    def __init__(self, on_hotkey):
        super().__init__()
        self._on_hotkey = on_hotkey

    def nativeEvent(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                self._on_hotkey(int(msg.wParam))
                return True, 0
        return super().nativeEvent(event_type, message)


class HotkeyManager(QObject):
    triggered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.receiver = _Receiver(self._dispatch)
        self.receiver.winId()  # 表示せずにウィンドウハンドルだけ作る
        self._actions: dict[int, str] = {}
        self._ids_by_action: dict[str, int] = {}

    def _hwnd(self) -> int:
        return int(self.receiver.winId())

    def id_for(self, action: str) -> int:
        return self._ids_by_action[action]

    def register_all(self, mapping: dict[str, str]) -> list[str]:
        """登録し直す。登録できなかった action 名（形式不正・他アプリと衝突）を返す。空欄は割り当てなし。"""
        self.unregister_all()
        failed = []
        for action, text in mapping.items():
            if not text:
                continue
            try:
                mods, vk = parse_hotkey(text)
            except ValueError:
                failed.append(action)
                continue
            hid = next(_ids)
            if _user32.RegisterHotKey(self._hwnd(), hid, mods, vk):
                self._actions[hid] = action
                self._ids_by_action[action] = hid
            else:
                failed.append(action)
        return failed

    def unregister_all(self) -> None:
        for hid in list(self._actions):
            _user32.UnregisterHotKey(self._hwnd(), hid)
        self._actions.clear()
        self._ids_by_action.clear()

    def _dispatch(self, hid: int) -> None:
        action = self._actions.get(hid)
        if action:
            self.triggered.emit(action)
