from __future__ import annotations

import math

from PySide6.QtCore import Qt, QPointF, QRectF, QSize, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QWidget,
)

_ICON_SZ = 26
_BTN_SZ = 36


def _icon_pan(size: int = _ICON_SZ) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = size / 2.0
    color = QColor(60, 185, 255)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    tip_r, base_r, aw = size * 0.44, size * 0.22, size * 0.17
    for deg in (0, 90, 180, 270):
        rad = math.radians(deg)
        dx, dy = math.sin(rad), -math.cos(rad)
        px, py = math.cos(rad), math.sin(rad)
        path = QPainterPath()
        path.moveTo(c + dx * tip_r, c + dy * tip_r)
        path.lineTo(c + dx * base_r - px * aw, c + dy * base_r - py * aw)
        path.lineTo(c + dx * base_r + px * aw, c + dy * base_r + py * aw)
        path.closeSubpath()
        p.drawPath(path)
    p.setBrush(QColor(60, 185, 255, 160))
    p.drawEllipse(QPointF(c, c), size * 0.11, size * 0.11)
    p.end()
    return QIcon(pix)


def _icon_marker(size: int = _ICON_SZ) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = size / 2.0
    color = QColor(55, 215, 100)
    pen = QPen(color, size * 0.10)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(c, c), size * 0.36, size * 0.36)
    pen2 = QPen(color, size * 0.08)
    p.setPen(pen2)
    h = size * 0.14
    p.drawLine(QPointF(c - h, c), QPointF(c + h, c))
    p.drawLine(QPointF(c, c - h), QPointF(c, c + h))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawEllipse(QPointF(c, c), size * 0.09, size * 0.09)
    p.end()
    return QIcon(pix)


def _icon_region(size: int = _ICON_SZ) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = size / 2.0
    n, r = 5, size * 0.40
    pen = QPen(QColor(255, 155, 35), size * 0.10)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(QColor(255, 155, 35, 50))
    path = QPainterPath()
    for i in range(n):
        a = math.radians(-90 + i * 360.0 / n)
        x, y = c + r * math.cos(a), c + r * math.sin(a)
        path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return QIcon(pix)


def _icon_select(size: int = _ICON_SZ) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(175, 105, 255)
    p.setPen(QPen(QColor(120, 55, 200), size * 0.06))
    p.setBrush(color)
    m, s = size * 0.10, size * 0.80
    path = QPainterPath()
    path.moveTo(m, m)
    path.lineTo(m, m + s * 0.64)
    path.lineTo(m + s * 0.24, m + s * 0.44)
    path.lineTo(m + s * 0.48, m + s * 0.78)
    path.lineTo(m + s * 0.62, m + s * 0.70)
    path.lineTo(m + s * 0.38, m + s * 0.36)
    path.lineTo(m + s * 0.52, m)
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return QIcon(pix)


def _icon_eye(size: int = _ICON_SZ) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = size / 2.0
    color = QColor(20, 220, 195)
    pen = QPen(color, size * 0.10)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    rx, ry = size * 0.42, size * 0.24
    path = QPainterPath()
    path.moveTo(c - rx, c)
    path.cubicTo(c - rx * 0.4, c - ry * 2.2, c + rx * 0.4, c - ry * 2.2, c + rx, c)
    path.cubicTo(c + rx * 0.4, c + ry * 2.2, c - rx * 0.4, c + ry * 2.2, c - rx, c)
    p.drawPath(path)
    p.setPen(QPen(color, size * 0.07))
    p.setBrush(QColor(20, 220, 195, 70))
    p.drawEllipse(QPointF(c, c), size * 0.16, size * 0.16)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawEllipse(QPointF(c, c), size * 0.07, size * 0.07)
    p.end()
    return QIcon(pix)


def _icon_box_marker(size: int = _ICON_SZ) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = size / 2.0
    color = QColor(55, 215, 100)
    sz = size * 0.54
    pen = QPen(color, size * 0.10)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    p.setPen(pen)
    p.setBrush(QColor(55, 215, 100, 45))
    p.drawRect(QRectF(c - sz / 2, c - sz / 2, sz, sz))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawEllipse(QPointF(c, c), size * 0.08, size * 0.08)
    p.end()
    return QIcon(pix)


def _icon_save(size: int = _ICON_SZ) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(80, 210, 130)
    pen = QPen(color, size * 0.12)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    c = size / 2.0
    p.drawLine(QPointF(c, size * 0.10), QPointF(c, size * 0.58))
    aw = size * 0.22
    p.drawLine(QPointF(c, size * 0.58), QPointF(c - aw, size * 0.38))
    p.drawLine(QPointF(c, size * 0.58), QPointF(c + aw, size * 0.38))
    m = size * 0.13
    p.drawLine(QPointF(m, size * 0.73), QPointF(m, size * 0.87))
    p.drawLine(QPointF(m, size * 0.87), QPointF(size - m, size * 0.87))
    p.drawLine(QPointF(size - m, size * 0.87), QPointF(size - m, size * 0.73))
    p.end()
    return QIcon(pix)


def _icon_load(size: int = _ICON_SZ) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(80, 160, 240)
    pen = QPen(color, size * 0.12)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    c = size / 2.0
    m = size * 0.13
    p.drawLine(QPointF(m, size * 0.73), QPointF(m, size * 0.87))
    p.drawLine(QPointF(m, size * 0.87), QPointF(size - m, size * 0.87))
    p.drawLine(QPointF(size - m, size * 0.87), QPointF(size - m, size * 0.73))
    p.drawLine(QPointF(c, size * 0.58), QPointF(c, size * 0.10))
    aw = size * 0.22
    p.drawLine(QPointF(c, size * 0.10), QPointF(c - aw, size * 0.30))
    p.drawLine(QPointF(c, size * 0.10), QPointF(c + aw, size * 0.30))
    p.end()
    return QIcon(pix)


def _icon_quit(size: int = _ICON_SZ) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(255, 75, 75), size * 0.17)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    m = size * 0.20
    p.drawLine(QPointF(m, m), QPointF(size - m, size - m))
    p.drawLine(QPointF(size - m, m), QPointF(m, size - m))
    p.end()
    return QIcon(pix)


def _make_tool_btn(icon: QIcon, tooltip: str, checkable: bool = True) -> QToolButton:
    btn = QToolButton()
    btn.setIcon(icon)
    btn.setIconSize(QSize(_ICON_SZ, _ICON_SZ))
    btn.setToolTip(tooltip)
    btn.setCheckable(checkable)
    btn.setFixedSize(_BTN_SZ, _BTN_SZ)
    btn.setStyleSheet(
        "QToolButton { background: #252525; border: 1px solid #3a3a3a; border-radius: 6px; }"
        "QToolButton:checked { background: #1e3a5f; border: 1px solid #4a9eff; }"
        "QToolButton:hover { background: #2e2e2e; border: 1px solid #555; }"
    )
    return btn


class AnnotationToolbar(QToolBar):
    tool_changed = Signal(str)
    annotations_toggled = Signal(bool)
    marker_box_toggled = Signal(bool)
    save_requested = Signal()
    load_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMovable(False)
        self.setStyleSheet(
            "QToolBar { background: #1a1a1a; border-bottom: 1px solid #333; spacing: 5px; }"
        )
        self._active_channel_name = ""
        self._build()

    def _build(self) -> None:
        self._pan_btn = _make_tool_btn(_icon_pan(), "Pan  [right-click drag in any mode]")
        self._marker_btn = _make_tool_btn(_icon_marker(), "Cell Marker: click to place")
        self._region_btn = _make_tool_btn(_icon_region(), "Region: drag to draw freehand")
        self._select_btn = _make_tool_btn(_icon_select(), "Select: click/drag to move · D to delete")
        self._eye_btn = _make_tool_btn(_icon_eye(), "Toggle annotations [Space]", checkable=True)
        self._eye_btn.setChecked(True)
        self._box_btn = _make_tool_btn(_icon_box_marker(), "Show markers as bounding boxes [B]", checkable=True)
        self._box_btn.setChecked(False)

        for btn in (self._pan_btn, self._marker_btn, self._region_btn, self._select_btn):
            self.addWidget(btn)

        self.addSeparator()
        self.addWidget(self._eye_btn)
        self.addWidget(self._box_btn)
        self.addSeparator()

        self._channel_lbl = QLabel("Channel: —")
        self._channel_lbl.setStyleSheet("color: #aaa; font-size: 12px; padding: 0 6px;")
        self.addWidget(self._channel_lbl)

        self._tool_buttons = {
            "pan": self._pan_btn,
            "cell_marker": self._marker_btn,
            "region": self._region_btn,
            "select": self._select_btn,
        }
        for name, btn in self._tool_buttons.items():
            btn.clicked.connect(lambda checked, n=name: self._on_tool_clicked(n))

        self._eye_btn.toggled.connect(self.annotations_toggled)
        self._box_btn.toggled.connect(self.marker_box_toggled)

        self.addSeparator()
        self._save_btn = _make_tool_btn(_icon_save(), "Save Annotations", checkable=False)
        self._load_btn = _make_tool_btn(_icon_load(), "Load Annotations", checkable=False)
        self._save_btn.setEnabled(False)
        self._load_btn.setEnabled(False)
        self._save_btn.clicked.connect(self.save_requested)
        self._load_btn.clicked.connect(self.load_requested)
        self.addWidget(self._save_btn)
        self.addWidget(self._load_btn)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        self._quit_btn = _make_tool_btn(_icon_quit(), "Quit", checkable=False)
        self._quit_btn.setStyleSheet(
            "QToolButton { background: #252525; border: 1px solid #3a3a3a; border-radius: 6px; }"
            "QToolButton:hover { background: #5a1515; border: 1px solid #f44; }"
        )
        self._quit_btn.clicked.connect(self.quit_requested)
        self.addWidget(self._quit_btn)

        self._pan_btn.setChecked(True)

    def _on_tool_clicked(self, name: str) -> None:
        for n, btn in self._tool_buttons.items():
            btn.setChecked(n == name)
        self.tool_changed.emit(name)

    def set_active_channel(self, name: str) -> None:
        self._active_channel_name = name
        self._channel_lbl.setText(f"Channel: {name}" if name else "Channel: —")

    def set_save_load_enabled(self, enabled: bool) -> None:
        self._save_btn.setEnabled(enabled)
        self._load_btn.setEnabled(enabled)

    def toggle_annotations_visibility(self) -> None:
        self._eye_btn.setChecked(not self._eye_btn.isChecked())
