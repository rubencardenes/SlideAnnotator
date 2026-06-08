from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsRectItem


class FOVItem(QGraphicsRectItem):
    """Field-of-view rectangle annotation."""

    def __init__(self, ann_id: str, x: float, y: float, w: float, h: float) -> None:
        super().__init__(x, y, w, h)
        self._ann_id = ann_id
        self._selected = False
        self._apply_style()
        self.setZValue(8)

    @property
    def ann_id(self) -> str:
        return self._ann_id

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self._apply_style()
            self.update()

    def _apply_style(self) -> None:
        fill = QColor(255, 220, 0, 50 if self._selected else 20)
        self.setBrush(QBrush(fill))
        pen = QPen(QColor(255, 220, 0))
        pen.setCosmetic(True)
        pen.setWidth(2 if self._selected else 1)
        self.setPen(pen)
