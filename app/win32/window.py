"""ウィンドウの Windows 固有の振る舞い。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget


def set_click_through(widget: QWidget, on: bool) -> None:
    """ON の間、マウス操作が背後のウィンドウに届くようにする。

    Qt の WindowTransparentForInput は Windows では WS_EX_TRANSPARENT|WS_EX_LAYERED
    を付ける。ウィンドウフラグの変更で一度非表示になるため、表示中なら出し直す
    （WA_ShowWithoutActivating を付けておけばフォーカスは奪わない）。
    """
    visible = widget.isVisible()
    widget.setWindowFlag(Qt.WindowType.WindowTransparentForInput, on)
    if visible:
        widget.show()
