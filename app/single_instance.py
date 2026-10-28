"""二重起動の防止。2つ目の起動は既存のアプリに「表示して」と伝えて終わる。"""
from __future__ import annotations

import getpass

from PySide6.QtCore import Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def default_name() -> str:
    return f"DigitalTimer-{getpass.getuser()}"


class InstanceServer(QLocalServer):
    show_requested = Signal()

    def __init__(self):
        super().__init__()
        self.newConnection.connect(self._on_connection)

    def _on_connection(self):
        # 中身は読まない: 2つ目の起動はすぐ切断するので、データより「接続が来た」ことを合図にする
        while self.hasPendingConnections():
            self.nextPendingConnection().deleteLater()
        self.show_requested.emit()


def acquire(name: str | None = None) -> InstanceServer | None:
    """最初の起動ならサーバを返す。既に起動中なら合図を送って None を返す。"""
    name = name or default_name()
    sock = QLocalSocket()
    sock.connectToServer(name)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return None
    server = InstanceServer()
    if not server.listen(name):
        # 前回の異常終了で名前が残っている場合は掃除してから取り直す
        QLocalServer.removeServer(name)
        server.listen(name)
    return server
