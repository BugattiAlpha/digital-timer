"""タスクトレイのアイコンとメニュー。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import theme

if TYPE_CHECKING:
    from ..controller import Controller


class Tray(QSystemTrayIcon):
    def __init__(self, controller: "Controller"):
        super().__init__(QIcon(str(theme.asset("images/icon.ico"))))
        self.c = controller
        self.setToolTip("Digital Timer")
        self.menu = QMenu()
        self.act_show = self.menu.addAction("表示 / 非表示", controller.toggle_visible)
        self.menu.addAction("お知らせを止める", controller.dismiss_alerts)
        self.menu.addSeparator()
        self.act_mini = self.menu.addAction("ミニ表示", controller.toggle_mini)
        self.act_click = self.menu.addAction("クリック透過", controller.toggle_click_through)
        self.act_top = self.menu.addAction("常に最前面", lambda: controller.set_always_on_top(
            not controller.settings.always_on_top))
        for act in (self.act_mini, self.act_click, self.act_top):
            act.setCheckable(True)
        self.menu.addSeparator()
        self.menu.addAction("設定…", controller.open_settings)
        self.menu.addAction("終了", controller.quit)
        self.menu.aboutToShow.connect(self._sync)
        self.setContextMenu(self.menu)
        self.activated.connect(self._on_activated)

    def _sync(self) -> None:
        self.act_mini.setChecked(self.c.settings.mini_mode)
        self.act_click.setChecked(self.c.click_through)
        self.act_top.setChecked(self.c.settings.always_on_top)

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.c.toggle_visible()

    def notify(self, title: str, message: str) -> None:
        self.showMessage(title, message, self.icon(), 6000)
