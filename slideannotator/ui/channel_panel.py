from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..compositing.compositor import ChannelSettings
from ..readers.protocol import ChannelInfo

_SLIDER_MAX = 65535


class _ColorButton(QPushButton):
    color_changed = Signal(tuple)

    def __init__(self, color: tuple[int, int, int], parent=None) -> None:
        super().__init__(parent)
        self._color = color
        self.setFixedSize(20, 20)
        self._update_style()
        self.clicked.connect(self._pick_color)

    def _update_style(self) -> None:
        r, g, b = self._color
        self.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); border: 1px solid #555; border-radius: 3px;"
        )

    def _pick_color(self) -> None:
        r, g, b = self._color
        initial = QColor(r, g, b)
        color = QColorDialog.getColor(initial, self, "Channel Color")
        if color.isValid():
            self._color = (color.red(), color.green(), color.blue())
            self._update_style()
            self.color_changed.emit(self._color)

    def set_color(self, color: tuple[int, int, int]) -> None:
        self._color = color
        self._update_style()


class ChannelRow(QFrame):
    visibility_changed = Signal(bool)
    color_changed = Signal(tuple)
    range_changed = Signal(float, float)
    selected = Signal()

    def __init__(
        self,
        info: ChannelInfo,
        settings: ChannelSettings,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._info = info
        self._settings = settings
        self._build_ui()

    def _build_ui(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "ChannelRow { border: 1px solid #333; border-radius: 4px; "
            "background: #252525; margin: 2px; }"
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(3)

        # Top row: checkbox + color + name
        top = QHBoxLayout()
        top.setSpacing(4)
        self._check = QCheckBox()
        self._check.setChecked(self._settings.visible)
        self._check.stateChanged.connect(
            lambda s: self.visibility_changed.emit(s != Qt.CheckState.Unchecked.value)
        )
        self._color_btn = _ColorButton(self._settings.color)
        self._color_btn.color_changed.connect(self.color_changed)
        name_lbl = QLabel(self._info.name)
        name_lbl.setStyleSheet("color: #ddd; font-size: 12px;")

        top.addWidget(self._check)
        top.addWidget(self._color_btn)
        top.addWidget(name_lbl)
        top.addStretch()
        layout.addLayout(top)

        slider_style = (
            "QSlider::groove:horizontal { height: 4px; background: #444; border-radius: 2px; }"
            "QSlider::handle:horizontal { width: 10px; height: 10px; margin: -3px 0; "
            "background: #7af; border-radius: 5px; }"
            "QSlider::sub-page:horizontal { background: #5af; border-radius: 2px; }"
        )
        lbl_style = "color: #888; font-size: 10px;"
        val_style = "color: #ccc; font-size: 10px; min-width: 38px;"

        # Min slider row
        min_row = QHBoxLayout()
        min_row.setSpacing(4)
        min_lbl = QLabel("Min")
        min_lbl.setStyleSheet(lbl_style)
        min_lbl.setFixedWidth(22)
        self._min_slider = QSlider(Qt.Orientation.Horizontal)
        self._min_slider.setRange(0, _SLIDER_MAX)
        self._min_slider.setValue(int(self._settings.min_val))
        self._min_slider.setStyleSheet(slider_style)
        self._min_val_lbl = QLabel(f"{int(self._settings.min_val)}")
        self._min_val_lbl.setStyleSheet(val_style)
        min_row.addWidget(min_lbl)
        min_row.addWidget(self._min_slider)
        min_row.addWidget(self._min_val_lbl)
        layout.addLayout(min_row)

        # Max slider row
        max_row = QHBoxLayout()
        max_row.setSpacing(4)
        max_lbl = QLabel("Max")
        max_lbl.setStyleSheet(lbl_style)
        max_lbl.setFixedWidth(22)
        self._max_slider = QSlider(Qt.Orientation.Horizontal)
        self._max_slider.setRange(0, _SLIDER_MAX)
        self._max_slider.setValue(int(self._settings.max_val))
        self._max_slider.setStyleSheet(slider_style)
        self._max_val_lbl = QLabel(f"{int(self._settings.max_val)}")
        self._max_val_lbl.setStyleSheet(val_style)
        max_row.addWidget(max_lbl)
        max_row.addWidget(self._max_slider)
        max_row.addWidget(self._max_val_lbl)
        layout.addLayout(max_row)

        self._min_slider.valueChanged.connect(self._on_min_changed)
        self._max_slider.valueChanged.connect(self._on_max_changed)

    def _on_min_changed(self, value: int) -> None:
        if value > self._max_slider.value():
            self._max_slider.setValue(value)
        self._min_val_lbl.setText(str(value))
        self.range_changed.emit(float(value), float(self._max_slider.value()))

    def _on_max_changed(self, value: int) -> None:
        if value < self._min_slider.value():
            self._min_slider.setValue(value)
        self._max_val_lbl.setText(str(value))
        self.range_changed.emit(float(self._min_slider.value()), float(value))

    def mousePressEvent(self, event) -> None:
        self.selected.emit()
        super().mousePressEvent(event)

    def set_active(self, active: bool) -> None:
        if active:
            self.setStyleSheet(
                "ChannelRow { border: 2px solid #5af; border-radius: 4px; "
                "background: #2a3040; margin: 2px; }"
            )
        else:
            self.setStyleSheet(
                "ChannelRow { border: 1px solid #333; border-radius: 4px; "
                "background: #252525; margin: 2px; }"
            )


class ChannelPanel(QWidget):
    channel_visibility_changed = Signal(int, bool)
    channel_color_changed = Signal(int, tuple)
    channel_range_changed = Signal(int, float, float)
    channel_selected = Signal(str)  # channel name

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[ChannelRow] = []
        self._active_index = 0
        self._build_ui()

    def _build_ui(self) -> None:
        self.setStyleSheet("background: #1e1e1e;")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header with title and select-all checkbox
        header = QHBoxLayout()
        header.setContentsMargins(8, 6, 8, 6)
        title = QLabel("Channels")
        title.setStyleSheet("color: #aaa; font-size: 12px; font-weight: bold;")
        self._select_all_check = QCheckBox("All")
        self._select_all_check.setChecked(True)
        self._select_all_check.setStyleSheet("color: #888; font-size: 11px;")
        self._select_all_check.stateChanged.connect(self._on_select_all)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._select_all_check)

        header_widget = QWidget()
        header_widget.setStyleSheet("background: #161616;")
        header_widget.setLayout(header)
        outer.addWidget(header_widget)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #1e1e1e; }")
        container = QWidget()
        self._list_layout = QVBoxLayout(container)
        self._list_layout.setContentsMargins(4, 4, 4, 4)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

    def _on_select_all(self, state: int) -> None:
        checked = state != Qt.CheckState.Unchecked.value
        for i, row in enumerate(self._rows):
            row._check.blockSignals(True)
            row._check.setChecked(checked)
            row._check.blockSignals(False)
            self.channel_visibility_changed.emit(i, checked)

    def load_channels(
        self, channels: list[ChannelInfo], settings: list[ChannelSettings]
    ) -> None:
        for row in self._rows:
            row.setParent(None)
        self._rows.clear()

        item = self._list_layout.takeAt(self._list_layout.count() - 1)
        del item

        for i, (ch, s) in enumerate(zip(channels, settings)):
            row = ChannelRow(ch, s)
            idx = i
            row.visibility_changed.connect(
                lambda v, i=idx: self.channel_visibility_changed.emit(i, v)
            )
            row.color_changed.connect(
                lambda c, i=idx: self.channel_color_changed.emit(i, c)
            )
            row.range_changed.connect(
                lambda mn, mx, i=idx: self.channel_range_changed.emit(i, mn, mx)
            )
            row.selected.connect(lambda i=idx: self._on_row_selected(i))
            self._list_layout.addWidget(row)
            self._rows.append(row)

        self._list_layout.addStretch()

        if self._rows:
            self._on_row_selected(0)

    def _on_row_selected(self, index: int) -> None:
        for i, row in enumerate(self._rows):
            row.set_active(i == index)
        self._active_index = index
        if index < len(self._rows):
            self.channel_selected.emit(self._rows[index]._info.name)
