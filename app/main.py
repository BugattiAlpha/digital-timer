"""起動: .venv\\Scripts\\pythonw.exe -m app.main"""
from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .controller import Controller
from .core.store import default_dir
from .single_instance import acquire
from .ui import theme


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Digital Timer")
    app.setQuitOnLastWindowClosed(False)  # ×ではトレイに残る
    app.setWindowIcon(QIcon(str(theme.asset("images/icon.ico"))))
    app.setStyleSheet(theme.stylesheet())
    theme.load_fonts()

    server = acquire()
    if server is None:
        return 0  # 既に起動しているアプリに「表示して」と伝えた

    controller = Controller(default_dir())
    server.show_requested.connect(controller.show_window)
    app.commitDataRequest.connect(lambda _m: controller.save())  # Windows のサインアウト時
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
