import ctypes

import pytest
from PySide6.QtWidgets import QWidget

from app.win32.hotkeys import HotkeyManager, parse_hotkey
from app.win32.window import set_click_through

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x20


def test_parse_ctrl_alt_letter():
    assert parse_hotkey("Ctrl+Alt+S") == (0x4003, 0x53)


def test_parse_shift_function_key_case_insensitive():
    assert parse_hotkey("ctrl+shift+f5") == (0x4006, 0x74)


def test_parse_digit_and_win():
    assert parse_hotkey("Win+Alt+3") == (0x4009, 0x33)


@pytest.mark.parametrize("bad", ["", "Alt+", "S", "Ctrl+Alt+Foo", "Ctrl+Alt+S+T"])
def test_parse_rejects_invalid(bad):
    with pytest.raises(ValueError):
        parse_hotkey(bad)


def test_register_and_conflict_does_not_crash(qtbot):
    a, b = HotkeyManager(), HotkeyManager()
    try:
        assert a.register_all({"x": "Ctrl+Alt+Shift+F24"}) == []
        # 同じキーは2つ目が登録できない → 失敗した action 名が返るだけで落ちない
        assert b.register_all({"x": "Ctrl+Alt+Shift+F24"}) == ["x"]
    finally:
        a.unregister_all()
        b.unregister_all()


def test_invalid_text_reported_as_failed(qtbot):
    m = HotkeyManager()
    try:
        assert m.register_all({"y": "nonsense"}) == ["y"]
    finally:
        m.unregister_all()


def test_unregister_frees_key(qtbot):
    a, b = HotkeyManager(), HotkeyManager()
    try:
        a.register_all({"x": "Ctrl+Alt+Shift+F23"})
        a.unregister_all()
        assert b.register_all({"x": "Ctrl+Alt+Shift+F23"}) == []
    finally:
        b.unregister_all()


def test_hotkey_message_emits_action(qtbot):
    m = HotkeyManager()
    try:
        m.register_all({"x": "Ctrl+Alt+Shift+F22"})
        with qtbot.waitSignal(m.triggered, timeout=2000) as sig:
            hwnd = int(m.receiver.winId())
            ctypes.windll.user32.PostMessageW(hwnd, 0x0312, m.id_for("x"), 0)
        assert sig.args == ["x"]
    finally:
        m.unregister_all()


def test_click_through_toggles_exstyle(qtbot):
    w = QWidget()
    qtbot.addWidget(w)
    w.show()
    get = ctypes.windll.user32.GetWindowLongPtrW
    get.restype = ctypes.c_ssize_t
    get.argtypes = [ctypes.c_void_p, ctypes.c_int]
    set_click_through(w, True)
    assert w.isVisible()
    assert get(int(w.winId()), GWL_EXSTYLE) & WS_EX_TRANSPARENT
    set_click_through(w, False)
    assert w.isVisible()
    assert not get(int(w.winId()), GWL_EXSTYLE) & WS_EX_TRANSPARENT


def test_empty_text_is_unassigned_not_failed(qtbot):
    # 空欄は「割り当てなし」。設定画面で「使用中」と出さない
    m = HotkeyManager()
    assert m.register_all({"toggle": ""}) == []
    m.unregister_all()
