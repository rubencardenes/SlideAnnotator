"""Programmatic application icon.

Drawn at runtime (rather than shipped as a binary asset) so it stays crisp at
every size the platform requests.  The motif is a dark fluorescence-microscopy
field with glowing multiplex-IF cells in the channel palette, one of them
encircled by a green annotation ring — a nod to the app's green outline colour
and its purpose of annotating cells.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)

# (x, y, radius, colour) as fractions of the icon side length.
_CELLS: list[tuple[float, float, float, QColor]] = [
    (0.31, 0.33, 0.110, QColor(70, 220, 140)),  # green   (the annotated cell)
    (0.68, 0.28, 0.090, QColor(90, 185, 255)),  # cyan
    (0.71, 0.66, 0.100, QColor(232, 96, 188)),  # magenta
    (0.41, 0.69, 0.072, QColor(255, 128, 96)),  # red / orange
]

_ANNOTATION_GREEN = QColor(60, 230, 128)


def _draw(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Rounded-square dark field with a subtle vertical gradient.
    radius = size * 0.22
    field = QPainterPath()
    field.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    bg = QLinearGradient(0, 0, 0, size)
    bg.setColorAt(0.0, QColor(18, 35, 43))
    bg.setColorAt(1.0, QColor(9, 14, 19))
    p.fillPath(field, QBrush(bg))

    # Keep every glow inside the rounded field.
    p.setClipPath(field)
    p.setPen(Qt.PenStyle.NoPen)

    for fx, fy, fr, colour in _CELLS:
        cx, cy, r = fx * size, fy * size, fr * size
        reach = r * 2.2
        glow = QRadialGradient(QPointF(cx, cy), reach)
        core = colour.lighter(150)
        edge = QColor(colour)
        edge.setAlpha(0)
        glow.setColorAt(0.0, core)
        glow.setColorAt(0.35, colour)
        glow.setColorAt(1.0, edge)
        p.setBrush(QBrush(glow))
        p.drawEllipse(QPointF(cx, cy), reach, reach)

        # Bright nucleus.
        p.setBrush(QBrush(colour.lighter(175)))
        p.drawEllipse(QPointF(cx, cy), r * 0.42, r * 0.42)

    # Green annotation ring around the first (green) cell.
    ax, ay, ar, _ = _CELLS[0]
    cx, cy, r = ax * size, ay * size, ar * size
    pen = QPen(_ANNOTATION_GREEN)
    pen.setWidthF(max(1.0, size * 0.028))
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(cx, cy), r * 1.65, r * 1.65)

    p.end()
    return pm


def make_app_icon() -> QIcon:
    """Return the application icon rendered at several sizes."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        icon.addPixmap(_draw(size))
    return icon
