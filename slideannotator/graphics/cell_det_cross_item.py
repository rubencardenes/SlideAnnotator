from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem

SCREEN_ARM = 5.0  # half-arm length in screen pixels


class CellDetCrossItem(QGraphicsItem):
    """Cross marker that stays constant in screen size at all zoom levels."""

    def __init__(self, color: QColor, screen_width: int = 2) -> None:
        super().__init__()
        self._color = color
        self._screen_width = screen_width
        self._br = QRectF(-2000, -2000, 4000, 4000)
        self.setZValue(16)

    def set_screen_width(self, w: int) -> None:
        self._screen_width = w
        self.update()

    def set_color(self, color: QColor) -> None:
        self._color = QColor(color)
        self.update()

    def boundingRect(self) -> QRectF:
        return self._br

    def paint(self, painter, option: QStyleOptionGraphicsItem, widget=None) -> None:
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        if lod < 1e-9:
            return
        arm = SCREEN_ARM / lod
        pen = QPen(self._color, self._screen_width / lod)
        pen.setCapStyle(pen.capStyle().RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(-arm, 0.0), QPointF(arm, 0.0))
        painter.drawLine(QPointF(0.0, -arm), QPointF(0.0, arm))
