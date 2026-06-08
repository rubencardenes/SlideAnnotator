from __future__ import annotations

from PySide6.QtCore import QRectF, QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QTransform
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem

SCREEN_RADIUS = 6.0
HALO_EXTRA = 3.0


class CellMarkerItem(QGraphicsItem):
    """Cell marker dot that renders at a constant screen size regardless of zoom."""

    def __init__(self, ann_id: str, color: QColor) -> None:
        super().__init__()
        self._ann_id = ann_id
        self._color = color
        self._selected = False
        # Large conservative bounding rect so Qt doesn't cull us at low zoom
        self._br = QRectF(-2000, -2000, 4000, 4000)
        self.setZValue(10)

    @property
    def ann_id(self) -> str:
        return self._ann_id

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self.update()

    def boundingRect(self) -> QRectF:
        return self._br

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget=None,
    ) -> None:
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        if lod < 1e-9:
            return
        r = SCREEN_RADIUS / lod

        if self._selected:
            halo_r = r + HALO_EXTRA / lod
            painter.setPen(QPen(QColor(255, 255, 255), 2.0 / lod))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(0, 0), halo_r, halo_r)

        painter.setPen(QPen(QColor(0, 0, 0, 180), 1.0 / lod))
        painter.setBrush(QBrush(self._color))
        painter.drawEllipse(QPointF(0, 0), r, r)

    def shape(self):
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.addEllipse(QPointF(0, 0), 2000, 2000)
        return path
