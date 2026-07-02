from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class MarkerSelectionDialog(QDialog):
    """Popup to select which markers (channels) to include in an export."""

    def __init__(
        self,
        channels: list[str],
        title: str = "Select Markers",
        parent=None,
        show_format_choice: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(320)
        self.setStyleSheet(
            "QDialog { background: #1e1e1e; }"
            "QLabel { color: #ccc; font-size: 12px; }"
            "QCheckBox { color: #ccc; font-size: 12px; spacing: 6px; }"
            "QCheckBox::indicator { width: 14px; height: 14px; }"
            "QDialogButtonBox QPushButton {"
            "  background: #2e2e2e; color: #ccc;"
            "  border: 1px solid #444; border-radius: 4px; padding: 4px 16px;"
            "}"
            "QDialogButtonBox QPushButton:hover { background: #3a3a3a; }"
        )

        self._channel_checkboxes: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 12, 14, 14)

        if not channels:
            layout.addWidget(QLabel("No markers found in the database."))
        else:
            # "Select all" toggle at the top
            self._select_all_cb = QCheckBox("Select / deselect all")
            self._select_all_cb.setTristate(False)
            self._select_all_cb.setStyleSheet(
                "QCheckBox { color: #999; font-size: 11px; font-style: italic; }"
            )
            self._select_all_cb.stateChanged.connect(self._on_select_all_changed)
            layout.addWidget(self._select_all_cb)

            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet("color: #3a3a3a;")
            layout.addWidget(sep)

            # Scrollable list of per-channel checkboxes
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setStyleSheet("QScrollArea { background: transparent; }")

            inner = QWidget()
            inner.setStyleSheet("background: transparent;")
            inner_layout = QVBoxLayout(inner)
            inner_layout.setSpacing(4)
            inner_layout.setContentsMargins(4, 4, 4, 4)

            for ch in channels:
                cb = QCheckBox(ch)
                cb.setChecked(False)
                cb.stateChanged.connect(self._on_item_changed)
                self._channel_checkboxes[ch] = cb
                inner_layout.addWidget(cb)

            inner_layout.addStretch()
            scroll.setWidget(inner)

            max_visible = 10
            row_height = 24
            scroll.setMaximumHeight(max_visible * row_height + 8)
            layout.addWidget(scroll)

        self._yolo_radio: QRadioButton | None = None
        self._coco_radio: QRadioButton | None = None
        if show_format_choice:
            sep2 = QFrame()
            sep2.setFrameShape(QFrame.Shape.HLine)
            sep2.setStyleSheet("color: #3a3a3a;")
            layout.addWidget(sep2)

            layout.addWidget(QLabel("Export format:"))
            format_row = QHBoxLayout()
            self._yolo_radio = QRadioButton("YOLO")
            self._coco_radio = QRadioButton("COCO")
            self._yolo_radio.setChecked(True)
            format_group = QButtonGroup(self)
            format_group.addButton(self._yolo_radio)
            format_group.addButton(self._coco_radio)
            format_row.addWidget(self._yolo_radio)
            format_row.addWidget(self._coco_radio)
            format_row.addStretch()
            layout.addLayout(format_row)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def selected_channels(self) -> list[str]:
        return [ch for ch, cb in self._channel_checkboxes.items() if cb.isChecked()]

    def export_format(self) -> str:
        if self._coco_radio is not None and self._coco_radio.isChecked():
            return "coco"
        return "yolo"

    def _on_select_all_changed(self, state: int) -> None:
        checked = state == Qt.CheckState.Checked.value
        for cb in self._channel_checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(checked)
            cb.blockSignals(False)

    def _on_item_changed(self) -> None:
        states = [cb.isChecked() for cb in self._channel_checkboxes.values()]
        self._select_all_cb.blockSignals(True)
        if all(states):
            self._select_all_cb.setCheckState(Qt.CheckState.Checked)
        elif any(states):
            self._select_all_cb.setCheckState(Qt.CheckState.PartiallyChecked)
        else:
            self._select_all_cb.setCheckState(Qt.CheckState.Unchecked)
        self._select_all_cb.blockSignals(False)
