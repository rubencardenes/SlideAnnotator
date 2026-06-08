from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon, QColor
from PySide6.QtWidgets import (
    QLabel,
    QToolBar,
    QToolButton,
    QWidget,
    QHBoxLayout,
    QSizePolicy,
)


def _make_icon_button(text: str, tooltip: str, checkable: bool = True) -> QToolButton:
    btn = QToolButton()
    btn.setText(text)
    btn.setToolTip(tooltip)
    btn.setCheckable(checkable)
    btn.setFixedSize(32, 32)
    btn.setStyleSheet(
        "QToolButton { background: #2a2a2a; color: #ccc; border: 1px solid #444; "
        "border-radius: 4px; font-size: 13px; }"
        "QToolButton:checked { background: #3a5a8a; border: 1px solid #5af; }"
        "QToolButton:hover { background: #353535; }"
    )
    return btn


class AnnotationToolbar(QToolBar):
    tool_changed = Signal(str)           # tool name
    annotations_toggled = Signal(bool)   # visible
    quit_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMovable(False)
        self.setStyleSheet(
            "QToolBar { background: #1a1a1a; border-bottom: 1px solid #333; spacing: 4px; }"
        )
        self._active_channel_name = ""
        self._build()

    def _build(self) -> None:
        self._pan_btn = _make_icon_button("⊕", "Pan (hold middle mouse in any mode)")
        self._marker_btn = _make_icon_button("●", "Cell Marker: click to place")
        self._region_btn = _make_icon_button("⬠", "Region: drag to draw freehand")
        self._select_btn = _make_icon_button("↖", "Select: click / drag to move / D to delete")
        self._eye_btn = _make_icon_button("◎", "Toggle annotation visibility", checkable=True)
        self._eye_btn.setChecked(True)

        for btn in (self._pan_btn, self._marker_btn, self._region_btn, self._select_btn):
            self.addWidget(btn)

        self.addSeparator()
        self.addWidget(self._eye_btn)
        self.addSeparator()

        self._channel_lbl = QLabel("Channel: —")
        self._channel_lbl.setStyleSheet("color: #aaa; font-size: 12px; padding: 0 6px;")
        self.addWidget(self._channel_lbl)

        # Wire buttons into exclusive group manually
        self._tool_buttons = {
            "pan": self._pan_btn,
            "cell_marker": self._marker_btn,
            "region": self._region_btn,
            "select": self._select_btn,
        }
        for name, btn in self._tool_buttons.items():
            btn.clicked.connect(lambda checked, n=name: self._on_tool_clicked(n))

        self._eye_btn.toggled.connect(self.annotations_toggled)

        # Spacer pushes quit button to the far right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        self._quit_btn = _make_icon_button("✕", "Quit", checkable=False)
        self._quit_btn.setStyleSheet(
            "QToolButton { background: #2a2a2a; color: #f77; border: 1px solid #444; "
            "border-radius: 4px; font-size: 13px; }"
            "QToolButton:hover { background: #5a1a1a; color: #faa; border: 1px solid #f55; }"
        )
        self._quit_btn.clicked.connect(self.quit_requested)
        self.addWidget(self._quit_btn)

        # Select pan by default
        self._pan_btn.setChecked(True)

    def _on_tool_clicked(self, name: str) -> None:
        for n, btn in self._tool_buttons.items():
            btn.setChecked(n == name)
        self.tool_changed.emit(name)

    def set_active_channel(self, name: str) -> None:
        self._active_channel_name = name
        self._channel_lbl.setText(f"Channel: {name}" if name else "Channel: —")
