from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QPushButton,
    QSpinBox,
)

_DEFAULT_COLOR = QColor(0, 230, 180)
_DEFAULT_WIDTH = 1


class StarDistSettingsDialog(QDialog):
    def __init__(self, color: QColor, width: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("StarDist Outline Settings")
        self.setModal(True)
        self.setStyleSheet(
            "QDialog { background: #222; color: #ccc; }"
            "QLabel { color: #ccc; }"
            "QSpinBox { background: #2a2a2a; color: #ccc; border: 1px solid #444;"
            "  border-radius: 4px; padding: 2px 4px; }"
            "QSpinBox::up-button, QSpinBox::down-button { background: #333; }"
            "QDialogButtonBox QPushButton { background: #2e2e2e; color: #ccc;"
            "  border: 1px solid #444; border-radius: 5px; padding: 4px 12px; }"
            "QDialogButtonBox QPushButton:hover { background: #3a3a3a; }"
        )
        self._color = QColor(color)

        layout = QFormLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(80, 26)
        self._color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_color_btn()
        self._color_btn.clicked.connect(self._pick_color)
        layout.addRow("Outline color:", self._color_btn)

        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, 10)
        self._width_spin.setValue(width)
        self._width_spin.setSuffix(" px")
        self._width_spin.setFixedWidth(80)
        layout.addRow("Line thickness:", self._width_spin)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _pick_color(self) -> None:
        c = QColorDialog.getColor(self._color, self, "Choose Outline Color")
        if c.isValid():
            self._color = c
            self._update_color_btn()

    def _update_color_btn(self) -> None:
        self._color_btn.setStyleSheet(
            f"background: {self._color.name()};"
            "border: 1px solid #666; border-radius: 4px;"
        )

    @property
    def selected_color(self) -> QColor:
        return self._color

    @property
    def selected_width(self) -> int:
        return self._width_spin.value()
