from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSlider,
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


def _icon_summary(size: int = _ICON_SZ) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(190, 150, 255)
    pen = QPen(color, size * 0.09)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    lx, rx = size * 0.18, size * 0.82
    bars = [
        (size * 0.20, size * 0.38, rx),  # top bar
        (size * 0.44, size * 0.54, rx * 0.78),  # middle bar (shorter)
        (size * 0.67, size * 0.70, rx * 0.58),  # bottom bar (shortest)
    ]
    dot_r = size * 0.055
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    for cy, _, _ in bars:
        p.drawEllipse(QPointF(lx, cy), dot_r, dot_r)
    pen2 = QPen(color, size * 0.09)
    pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen2)
    for cy, _, bar_rx in bars:
        p.drawLine(QPointF(lx + dot_r * 2.2, cy), QPointF(bar_rx, cy))
    p.end()
    return QIcon(pix)


def _icon_cell_det_to_annot(size: int = _ICON_SZ) -> QIcon:
    """Cross → rectangle: convert detections to region annotations."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(255, 100, 80)

    # Cross on the left
    arm = size * 0.12
    cx_c, cy_c = size * 0.22, size * 0.50
    pen = QPen(color, size * 0.09)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(cx_c - arm, cy_c), QPointF(cx_c + arm, cy_c))
    p.drawLine(QPointF(cx_c, cy_c - arm), QPointF(cx_c, cy_c + arm))

    # Arrow in the middle
    pen2 = QPen(color, size * 0.07)
    pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen2)
    ax1, ax2, ay = size * 0.38, size * 0.56, size * 0.50
    p.drawLine(QPointF(ax1, ay), QPointF(ax2, ay))
    ah = size * 0.08
    p.drawLine(QPointF(ax2 - ah, ay - ah), QPointF(ax2, ay))
    p.drawLine(QPointF(ax2 - ah, ay + ah), QPointF(ax2, ay))

    # Rectangle on the right
    pen3 = QPen(color, size * 0.09)
    pen3.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    p.setPen(pen3)
    p.setBrush(QColor(255, 100, 80, 40))
    rw, rh = size * 0.28, size * 0.36
    p.drawRect(QRectF(size * 0.65, size * 0.50 - rh / 2, rw, rh))

    p.end()
    return QIcon(pix)


def _icon_stardist_run(size: int = _ICON_SZ) -> QIcon:
    """Nuclear polygon blob — resembles a cell nucleus outline."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = size / 2.0
    color = QColor(0, 230, 180)

    # Smooth organic nucleus shape via Catmull-Rom through 8 irregular radii
    n = 8
    rs = [0.40, 0.34, 0.41, 0.36, 0.43, 0.35, 0.39, 0.37]
    pts = [
        (
            c + size * rs[i] * math.cos(math.radians(i * 360.0 / n - 70)),
            c + size * rs[i] * math.sin(math.radians(i * 360.0 / n - 70)),
        )
        for i in range(n)
    ]
    path = QPainterPath()
    path.moveTo(*pts[0])
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        cp1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        cp2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        path.cubicTo(cp1[0], cp1[1], cp2[0], cp2[1], p2[0], p2[1])
    path.closeSubpath()

    pen = QPen(color, size * 0.10)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(QColor(0, 230, 180, 45))
    p.drawPath(path)
    # Nucleolus dot
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawEllipse(QPointF(c - size * 0.07, c - size * 0.04), size * 0.09, size * 0.09)
    p.end()
    return QIcon(pix)


def _icon_stardist_toggle(size: int = _ICON_SZ) -> QIcon:
    """Eye icon in orange — toggle StarDist polygon visibility."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = size / 2.0
    color = QColor(255, 165, 30)
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
    p.setBrush(QColor(255, 165, 30, 70))
    p.drawEllipse(QPointF(c, c), size * 0.16, size * 0.16)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawEllipse(QPointF(c, c), size * 0.07, size * 0.07)
    p.end()
    return QIcon(pix)


def _icon_cell_det_run(size: int = _ICON_SZ) -> QIcon:
    """Several small crosses — object detection / cell dots."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(255, 100, 80)
    pen = QPen(color, size * 0.09)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    arm = size * 0.13
    centres = [
        (size * 0.28, size * 0.28),
        (size * 0.72, size * 0.34),
        (size * 0.38, size * 0.70),
        (size * 0.68, size * 0.68),
    ]
    for cx, cy in centres:
        p.drawLine(QPointF(cx - arm, cy), QPointF(cx + arm, cy))
        p.drawLine(QPointF(cx, cy - arm), QPointF(cx, cy + arm))
    p.end()
    return QIcon(pix)


def _icon_cell_det_toggle(size: int = _ICON_SZ) -> QIcon:
    """Eye icon in coral red — toggle cell detection visibility."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = size / 2.0
    color = QColor(255, 100, 80)
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
    p.setBrush(QColor(255, 100, 80, 70))
    p.drawEllipse(QPointF(c, c), size * 0.16, size * 0.16)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawEllipse(QPointF(c, c), size * 0.07, size * 0.07)
    p.end()
    return QIcon(pix)


def _icon_stardist_settings(size: int = _ICON_SZ) -> QIcon:
    """Gear icon for StarDist outline settings."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = size / 2.0
    color = QColor(190, 190, 190)

    n_teeth = 7
    outer_r = size * 0.44
    inner_r = size * 0.30
    hole_r = size * 0.13
    tooth_half = math.pi / n_teeth * 0.42  # half angular width of each tooth top

    gear = QPainterPath()
    for i in range(n_teeth):
        a_mid = math.radians(i * 360.0 / n_teeth)
        angles = [
            (inner_r, a_mid - tooth_half * 1.8),
            (outer_r, a_mid - tooth_half),
            (outer_r, a_mid + tooth_half),
            (inner_r, a_mid + tooth_half * 1.8),
        ]
        for j, (r, a) in enumerate(angles):
            x, y = c + r * math.cos(a), c + r * math.sin(a)
            gear.moveTo(x, y) if (i == 0 and j == 0) else gear.lineTo(x, y)
    gear.closeSubpath()

    # Punch center hole via even-odd fill rule
    gear.setFillRule(Qt.FillRule.OddEvenFill)
    gear.addEllipse(QPointF(c, c), hole_r, hole_r)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawPath(gear)
    p.end()
    return QIcon(pix)


def _icon_undo(size: int = _ICON_SZ) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(255, 200, 60)
    c, r = size / 2.0, size * 0.33
    pen = QPen(color, size * 0.10)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # CCW 270° arc: right → top → left → bottom; gap at lower-right
    p.drawArc(QRectF(c - r, c - r, r * 2, r * 2), 0, int(270 * 16))
    # Arrowhead at 270° (bottom), CCW tangent → pointing right
    ax, ay = c, c + r
    head = size * 0.14
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    path = QPainterPath()
    path.moveTo(ax + head, ay)
    path.lineTo(ax, ay - head * 0.65)
    path.lineTo(ax, ay + head * 0.65)
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return QIcon(pix)


def _icon_redo(size: int = _ICON_SZ) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(255, 200, 60)
    c, r = size / 2.0, size * 0.33
    pen = QPen(color, size * 0.10)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # CW 270° arc: left → top → right → bottom; gap at lower-left
    p.drawArc(QRectF(c - r, c - r, r * 2, r * 2), int(180 * 16), int(-270 * 16))
    # Arrowhead at 270° (bottom), CW tangent → pointing left
    ax, ay = c, c + r
    head = size * 0.14
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    path = QPainterPath()
    path.moveTo(ax - head, ay)
    path.lineTo(ax, ay - head * 0.65)
    path.lineTo(ax, ay + head * 0.65)
    path.closeSubpath()
    p.drawPath(path)
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
    region_opacity_changed = Signal(float)
    save_requested = Signal()
    load_requested = Signal()
    summary_requested = Signal()
    run_stardist_requested = Signal()
    stardist_toggled = Signal(bool)
    run_cell_det_requested = Signal()
    cell_det_toggled = Signal(bool)
    cell_det_to_annot_requested = Signal()
    quit_requested = Signal()
    undo_requested = Signal()
    redo_requested = Signal()
    stardist_settings_requested = Signal()

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
        self._select_btn = _make_tool_btn(
            _icon_select(), "Select: click/drag to move · D to delete"
        )
        self._eye_btn = _make_tool_btn(_icon_eye(), "Toggle annotations [Space]", checkable=True)
        self._eye_btn.setChecked(True)
        self._box_btn = _make_tool_btn(
            _icon_box_marker(), "Show markers as bounding boxes [B]", checkable=True
        )
        self._box_btn.setChecked(False)

        self._undo_btn = _make_tool_btn(_icon_undo(), "Undo [Ctrl+Z]", checkable=False)
        self._redo_btn = _make_tool_btn(_icon_redo(), "Redo [Ctrl+Shift+Z]", checkable=False)
        self._undo_btn.setEnabled(False)
        self._redo_btn.setEnabled(False)
        self._undo_btn.clicked.connect(self.undo_requested)
        self._redo_btn.clicked.connect(self.redo_requested)

        for btn in (self._pan_btn, self._marker_btn, self._region_btn, self._select_btn):
            self.addWidget(btn)

        self.addSeparator()
        self.addWidget(self._undo_btn)
        self.addWidget(self._redo_btn)
        self.addSeparator()
        self.addWidget(self._eye_btn)
        self.addWidget(self._box_btn)
        self.addSeparator()

        # Region fill-opacity slider
        _DEFAULT_OPACITY = 16  # ≈ alpha 40/255 — matches current hardcoded default
        opacity_widget = QWidget()
        opacity_layout = QHBoxLayout(opacity_widget)
        opacity_layout.setContentsMargins(4, 0, 4, 0)
        opacity_layout.setSpacing(4)
        opacity_lbl = QLabel("Fill:")
        opacity_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        self._region_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._region_opacity_slider.setRange(0, 100)
        self._region_opacity_slider.setValue(_DEFAULT_OPACITY)
        self._region_opacity_slider.setFixedWidth(80)
        self._region_opacity_slider.setToolTip("Region fill opacity")
        self._region_opacity_slider.setStyleSheet(
            "QSlider::groove:horizontal { height: 4px; background: #444; border-radius: 2px; }"
            "QSlider::handle:horizontal { width: 10px; height: 10px; margin: -3px 0; "
            "background: #f90; border-radius: 5px; }"
            "QSlider::sub-page:horizontal { background: #f90; border-radius: 2px; }"
        )
        self._region_opacity_val_lbl = QLabel(f"{_DEFAULT_OPACITY}%")
        self._region_opacity_val_lbl.setStyleSheet("color: #888; font-size: 11px; min-width: 28px;")
        self._region_opacity_slider.valueChanged.connect(self._on_region_opacity_slider)
        opacity_layout.addWidget(opacity_lbl)
        opacity_layout.addWidget(self._region_opacity_slider)
        opacity_layout.addWidget(self._region_opacity_val_lbl)
        self.addWidget(opacity_widget)
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
        self._summary_btn = _make_tool_btn(_icon_summary(), "Annotation Summary", checkable=False)
        self._save_btn.setEnabled(False)
        self._load_btn.setEnabled(False)
        self._summary_btn.setEnabled(False)
        self._save_btn.clicked.connect(self.save_requested)
        self._load_btn.clicked.connect(self.load_requested)
        self._summary_btn.clicked.connect(self.summary_requested)
        self.addWidget(self._save_btn)
        self.addWidget(self._load_btn)
        self.addWidget(self._summary_btn)

        self.addSeparator()
        self._stardist_run_btn = _make_tool_btn(
            _icon_stardist_run(), "Run StarDist on FOVs", checkable=False
        )
        self._stardist_toggle_btn = _make_tool_btn(
            _icon_stardist_toggle(), "Toggle StarDist nuclei [orange eye]", checkable=True
        )
        self._stardist_settings_btn = _make_tool_btn(
            _icon_stardist_settings(), "StarDist outline settings", checkable=False
        )
        self._stardist_toggle_btn.setChecked(True)
        self._stardist_run_btn.setEnabled(False)
        self._stardist_toggle_btn.setEnabled(False)
        self._stardist_settings_btn.setEnabled(False)
        self._stardist_run_btn.clicked.connect(self.run_stardist_requested)
        self._stardist_toggle_btn.toggled.connect(self.stardist_toggled)
        self._stardist_settings_btn.clicked.connect(self.stardist_settings_requested)
        self.addWidget(self._stardist_run_btn)
        self.addWidget(self._stardist_toggle_btn)
        self.addWidget(self._stardist_settings_btn)

        self.addSeparator()
        self._cell_det_run_btn = _make_tool_btn(
            _icon_cell_det_run(), "Run Cell Detection on FOVs", checkable=False
        )
        self._cell_det_toggle_btn = _make_tool_btn(
            _icon_cell_det_toggle(), "Toggle cell detections [coral eye]", checkable=True
        )
        self._cell_det_to_annot_btn = _make_tool_btn(
            _icon_cell_det_to_annot(), "Convert detections to region annotations", checkable=False
        )
        self._cell_det_toggle_btn.setChecked(True)
        self._cell_det_run_btn.setEnabled(False)
        self._cell_det_toggle_btn.setEnabled(False)
        self._cell_det_to_annot_btn.setEnabled(False)
        self._cell_det_run_btn.clicked.connect(self.run_cell_det_requested)
        self._cell_det_toggle_btn.toggled.connect(self.cell_det_toggled)
        self._cell_det_to_annot_btn.clicked.connect(self.cell_det_to_annot_requested)
        self.addWidget(self._cell_det_run_btn)
        self.addWidget(self._cell_det_toggle_btn)
        self.addWidget(self._cell_det_to_annot_btn)

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

    def _on_region_opacity_slider(self, value: int) -> None:
        self._region_opacity_val_lbl.setText(f"{value}%")
        self.region_opacity_changed.emit(value / 100.0)

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
        self._summary_btn.setEnabled(enabled)
        self._stardist_run_btn.setEnabled(enabled)
        self._stardist_toggle_btn.setEnabled(enabled)
        self._stardist_settings_btn.setEnabled(enabled)
        self._cell_det_run_btn.setEnabled(enabled)
        self._cell_det_toggle_btn.setEnabled(enabled)

    def set_cell_det_convert_enabled(self, enabled: bool) -> None:
        self._cell_det_to_annot_btn.setEnabled(enabled)

    def set_stardist_running(self, running: bool) -> None:
        self._stardist_run_btn.setEnabled(not running)

    def set_cell_det_running(self, running: bool) -> None:
        self._cell_det_run_btn.setEnabled(not running)

    def toggle_annotations_visibility(self) -> None:
        self._eye_btn.setChecked(not self._eye_btn.isChecked())

    def set_undo_redo_enabled(self, can_undo: bool, can_redo: bool) -> None:
        self._undo_btn.setEnabled(can_undo)
        self._redo_btn.setEnabled(can_redo)
