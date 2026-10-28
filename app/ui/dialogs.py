"""タイマーの追加/編集ダイアログと設定ダイアログ（暗色テーマ）。"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from PySide6.QtCore import QTime, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QGridLayout, QHBoxLayout, QKeySequenceEdit, QLabel,
                               QLineEdit, QPushButton, QRadioButton, QSlider, QSpinBox,
                               QStackedWidget, QTimeEdit, QVBoxLayout, QWidget)

from ..core.settings import HOTKEY_LABELS, MIN_OPACITY
from ..core.timers import Kind, TimerSpec, validate
from . import theme
from .alerts import SOUND_NAMES
from .display import KIND_LABELS

if TYPE_CHECKING:
    from ..controller import Controller


def _spin(lo: int, hi: int, suffix: str, value: int) -> QSpinBox:
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setSuffix(suffix)
    s.setValue(value)
    s.setAlignment(Qt.AlignmentFlag.AlignRight)
    return s


class TimerEditDialog(QDialog):
    def __init__(self, spec: TimerSpec | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("タイマーの編集" if spec else "タイマーの追加")
        self.setMinimumWidth(360)
        self._id = spec.id if spec else uuid.uuid4().hex[:12]

        self.kind_group = QButtonGroup(self)
        kinds = QHBoxLayout()
        self._kind_buttons: dict[Kind, QRadioButton] = {}
        for kind in Kind:
            b = QRadioButton(KIND_LABELS[kind])
            self.kind_group.addButton(b)
            self._kind_buttons[kind] = b
            kinds.addWidget(b)
            b.toggled.connect(self._on_kind_toggled)

        self.name = QLineEdit()
        self.name.setPlaceholderText("例: 会議、休憩、パスタ（空欄なら種類の名前）")
        self.color = QComboBox()
        for key, label in theme.TIMER_COLOR_LABELS.items():
            self.color.addItem(label, key)
        self.sound = QCheckBox("終了時に音を鳴らす")
        self.sound.setChecked(True)

        # 種類ごとの入力欄
        self.stack = QStackedWidget()
        self.stack.addWidget(QLabel("ストップウォッチは時間の入力はいりません。"))
        cd = QWidget()
        cd_lay = QGridLayout(cd)
        cd_lay.setContentsMargins(0, 0, 0, 0)
        self.cd_h, self.cd_m, self.cd_s = _spin(0, 99, " 時間", 0), _spin(0, 59, " 分", 5), _spin(0, 59, " 秒", 0)
        self.cd_repeat = QCheckBox("終わったら自動でもう一度始める（繰り返し）")
        cd_lay.addWidget(self.cd_h, 0, 0)
        cd_lay.addWidget(self.cd_m, 0, 1)
        cd_lay.addWidget(self.cd_s, 0, 2)
        cd_lay.addWidget(self.cd_repeat, 1, 0, 1, 3)
        self.stack.addWidget(cd)
        po = QWidget()
        po_lay = QFormLayout(po)
        po_lay.setContentsMargins(0, 0, 0, 0)
        self.po_work, self.po_rest = _spin(1, 600, " 分", 25), _spin(1, 600, " 分", 5)
        self.po_sets = _spin(0, 99, " セット", 4)
        self.po_sets.setSpecialValueText("無限")
        po_lay.addRow("作業時間", self.po_work)
        po_lay.addRow("休憩時間", self.po_rest)
        po_lay.addRow("くり返し", self.po_sets)
        self.stack.addWidget(po)
        self.al_page = QWidget()
        al_lay = QFormLayout(self.al_page)
        al_lay.setContentsMargins(0, 0, 0, 0)
        self.al_time = QTimeEdit(QTime(QTime.currentTime().hour(), 0).addSecs(3600))  # 次の正時
        self.al_time.setDisplayFormat("HH:mm")
        self.al_time.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.al_repeat = QCheckBox("毎日この時刻に鳴らす（繰り返し）")
        al_note = QLabel("保存するとすぐに動き始めます。過ぎた時刻なら翌日のその時刻に鳴ります。")
        al_note.setObjectName("caption")
        al_note.setWordWrap(True)
        al_lay.addRow("時刻", self.al_time)
        al_lay.addRow(self.al_repeat)
        al_lay.addRow(al_note)
        self.stack.addWidget(self.al_page)

        self.error = QLabel()
        self.error.setObjectName("error")
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                        | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("保存")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("キャンセル")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        # 何のタイマーか分かるよう、名前を先頭に置いて開いたらすぐ入力できるようにする
        self.form = QFormLayout()
        self.form.addRow("名前", self.name)
        self.form.addRow("種類", kinds)
        self.form.addRow("色", self.color)
        lay = QVBoxLayout(self)
        lay.addLayout(self.form)
        lay.addWidget(self.stack)
        lay.addWidget(self.sound)
        lay.addWidget(self.error)
        lay.addWidget(self.buttons)

        for w in (self.cd_h, self.cd_m, self.cd_s, self.po_work, self.po_rest, self.po_sets):
            w.valueChanged.connect(self._validate)
        self.name.textChanged.connect(self._validate)
        self.al_time.timeChanged.connect(self._validate)

        if spec:
            self._load(spec)
        else:
            self.set_kind(Kind.COUNTDOWN)
        self._validate()
        self.name.setFocus()

    def _load(self, spec: TimerSpec) -> None:
        self.set_kind(spec.kind)
        self.name.setText(spec.name)
        self.color.setCurrentIndex(max(0, self.color.findData(spec.color)))
        self.sound.setChecked(spec.sound)
        total = int(spec.duration)
        self.cd_h.setValue(total // 3600)
        self.cd_m.setValue(total % 3600 // 60)
        self.cd_s.setValue(total % 60)
        self.cd_repeat.setChecked(spec.repeat)
        if spec.kind == Kind.POMODORO:
            self.po_work.setValue(max(1, round(spec.work / 60)))
            self.po_rest.setValue(max(1, round(spec.rest / 60)))
            self.po_sets.setValue(spec.sets)
        if spec.kind == Kind.ALARM:
            t = QTime.fromString(spec.target, "HH:mm")
            if t.isValid():
                self.al_time.setTime(t)
            self.al_repeat.setChecked(spec.repeat)
            self.cd_repeat.setChecked(False)

    def set_kind(self, kind: Kind) -> None:
        self._kind_buttons[kind].setChecked(True)

    def kind(self) -> Kind:
        for kind, b in self._kind_buttons.items():
            if b.isChecked():
                return kind
        return Kind.COUNTDOWN

    def _on_kind_toggled(self, checked: bool) -> None:
        if not checked:
            return
        kind = self.kind()
        self.stack.setCurrentIndex(list(Kind).index(kind))
        self._validate()

    def get_spec(self) -> TimerSpec:
        kind = self.kind()
        return TimerSpec(
            id=self._id, kind=kind, name=self.name.text().strip() or KIND_LABELS[kind],
            color=self.color.currentData(),
            duration=self.cd_h.value() * 3600 + self.cd_m.value() * 60 + self.cd_s.value(),
            repeat=(self.al_repeat if kind == Kind.ALARM else self.cd_repeat).isChecked(),
            work=self.po_work.value() * 60, rest=self.po_rest.value() * 60,
            sets=self.po_sets.value(), sound=self.sound.isChecked(),
            target=self.al_time.time().toString("HH:mm") if kind == Kind.ALARM else "")

    def _validate(self) -> None:
        if not hasattr(self, "buttons"):
            return
        msg = validate(self.get_spec())
        self.error.setText(msg or "")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(msg is None)


class SettingsDialog(QDialog):
    def __init__(self, controller: "Controller", parent: QWidget | None = None):
        super().__init__(parent)
        self.c = controller
        s = controller.settings
        self.setWindowTitle("設定")
        self.setMinimumWidth(420)

        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(int(MIN_OPACITY * 100), 100)
        self.opacity.setValue(round(s.opacity * 100))
        self.opacity_label = QLabel()
        self.opacity.valueChanged.connect(self._on_opacity)
        self._on_opacity(self.opacity.value())
        op_row = QHBoxLayout()
        op_row.addWidget(self.opacity, 1)
        op_row.addWidget(self.opacity_label)

        self.on_top = QCheckBox("常に最前面に表示")
        self.on_top.setChecked(s.always_on_top)
        self.on_top.toggled.connect(controller.set_always_on_top)

        self.sound = QComboBox()
        for key, label in SOUND_NAMES.items():
            self.sound.addItem(label, key)
        self.sound.setCurrentIndex(max(0, self.sound.findData(s.sound_name)))
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(round(s.volume * 100))
        test = QPushButton("試聴")
        test.clicked.connect(self._preview)
        self.sound.currentIndexChanged.connect(self._apply_sound)
        self.volume.valueChanged.connect(self._apply_sound)
        snd_row = QHBoxLayout()
        snd_row.addWidget(self.sound)
        snd_row.addWidget(self.volume, 1)
        snd_row.addWidget(test)

        form = QFormLayout()
        form.addRow("透明度", op_row)
        form.addRow("", self.on_top)
        form.addRow("アラーム音", snd_row)

        keys = QGridLayout()
        self.key_edits: dict[str, QKeySequenceEdit] = {}
        self.key_status: dict[str, QLabel] = {}
        for row, (action, label) in enumerate(HOTKEY_LABELS.items()):
            edit = QKeySequenceEdit(QKeySequence(s.hotkeys.get(action, "")))
            edit.setMaximumSequenceLength(1)
            status = QLabel()
            status.setObjectName("error")
            keys.addWidget(QLabel(label), row, 0)
            keys.addWidget(edit, row, 1)
            keys.addWidget(status, row, 2)
            self.key_edits[action] = edit
            self.key_status[action] = status
        self._show_key_status(controller.hotkey_failures)

        caption = QLabel("ショートカットは他のアプリを使っている最中でも効きます。"
                         "「使用中」は他のアプリが同じキーを使っているため登録できなかったものです。"
                         "この画面を開いている間はショートカットは効きません。")
        caption.setObjectName("caption")
        caption.setWordWrap(True)

        buttons = QDialogButtonBox()
        save = buttons.addButton("ショートカットを保存", QDialogButtonBox.ButtonRole.ApplyRole)
        save.setObjectName("primary")
        save.clicked.connect(self._save_keys)
        close = buttons.addButton("閉じる", QDialogButtonBox.ButtonRole.RejectRole)
        close.clicked.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addSpacing(8)
        lay.addWidget(QLabel("ショートカット"))
        lay.addLayout(keys)
        lay.addWidget(caption)
        lay.addWidget(buttons)

    def _on_opacity(self, value: int) -> None:
        self.opacity_label.setText(f"{value}%")
        self.c.set_opacity(value / 100)

    def _apply_sound(self) -> None:
        self.c.set_sound(self.sound.currentData(), self.volume.value() / 100)

    def _preview(self) -> None:
        self._apply_sound()
        self.c.alerts.preview(self.sound.currentData(), self.volume.value() / 100)

    def _show_key_status(self, failed: list[str]) -> None:
        for action, label in self.key_status.items():
            label.setText("使用中" if action in failed else "")

    def _save_keys(self) -> None:
        mapping = {a: e.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
                   for a, e in self.key_edits.items()}
        self._show_key_status(self.c.apply_hotkeys(mapping))
