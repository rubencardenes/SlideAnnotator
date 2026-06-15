from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem

from ..annotations.models import MARKER_BOX_HALF

SCREEN_RADIUS = 6.0
HALO_EXTRA = 3.0


class CellMarkerItem(QGraphicsItem):
    """Cell marker dot/box that renders at a constant screen size (dot) or actual
    scene-space bounding-box size (box) depending on display mode."""

    def __init__(self, ann_id: str, color: QColor) -> None:
        super().__init__()
        self._ann_id = ann_id
        self._color = color
        self._selected = False
        self._show_box = False
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

    def set_show_box(self, show: bool) -> None:
        if self._show_box != show:
            self._show_box = show
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

        if self._show_box:
            # Draw the actual bounding box in scene space (minimum SCREEN_RADIUS screen px)
            r = max(SCREEN_RADIUS / lod, float(MARKER_BOX_HALF))
            rect = QRectF(-r, -r, r * 2, r * 2)
            pen = QPen(self._color, 1.5 / lod)
            if self._selected:
                pen.setColor(QColor(255, 255, 255))
                pen.setWidth(2.5 / lod)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
        else:
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
