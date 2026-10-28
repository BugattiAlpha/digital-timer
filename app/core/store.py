"""設定とタイマー一覧を JSON で保存・復元する。"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from .settings import Settings
from .timers import TimerRuntime, validate

log = logging.getLogger(__name__)
FILE_NAME = "state.json"


def default_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "DigitalTimer"


class Store:
    def __init__(self, directory: Path):
        self.dir = Path(directory)
        self.path = self.dir / FILE_NAME

    def load(self) -> tuple[Settings, list[TimerRuntime]]:
        if not self.path.exists():
            return Settings(), []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("state.json の中身がオブジェクトではない")
            settings = Settings.from_dict(data.get("settings") or {})
        except (OSError, ValueError, TypeError, AttributeError) as e:
            # 壊れたファイルは残しておき（原因調査用）、既定値で起動する
            log.warning("state.json を読めないため退避します: %s", e)
            os.replace(self.path, self.path.with_name(FILE_NAME + ".bak"))
            return Settings(), []
        items = data.get("timers")
        timers = []
        for item in items if isinstance(items, list) else []:
            try:
                runtime = TimerRuntime.from_dict(item)
            except (KeyError, ValueError, TypeError, AttributeError) as e:
                log.warning("読めないタイマーを読み飛ばします: %s", e)
                continue
            # 0秒の繰り返しなど、ダイアログでは作れない値は動かすと壊れるので読み込まない
            error = validate(runtime.spec)
            if error:
                log.warning("不正なタイマーを読み飛ばします: %s", error)
                continue
            timers.append(runtime)
        return settings, timers

    def save(self, settings: Settings, runtimes: list[TimerRuntime], now: float) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "settings": settings.to_dict(),
            "timers": [r.to_dict(now) for r in runtimes],
        }
        tmp = self.path.with_name(FILE_NAME + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)
