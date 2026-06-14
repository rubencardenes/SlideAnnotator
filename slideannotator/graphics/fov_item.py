from __future__ import annotations

from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsSimpleTextItem


class FOVItem(QGraphicsRectItem):
    """Field-of-view rectangle annotation."""

    def __init__(self, ann_id: str, x: float, y: float, w: float, h: float, color: QColor, label: str = "") -> None:
        self._label: QGraphicsSimpleTextItem | None = None  # guard before super().__init__
        super().__init__(x, y, w, h)
        self._ann_id = ann_id
        self._color = QColor(color)
        self._selected = False
        self._apply_style()
        self.setZValue(8)

        if label:
            self._label = QGraphicsSimpleTextItem(label, self)
            self._label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            self._label.setPos(x, y)
            self._label.setBrush(QBrush(self._color))
            self._label.setZValue(9)

    def setRect(self, *args) -> None:
        super().setRect(*args)
        if self._label is not None:
            r = self.rect()
            self._label.setPos(r.x(), r.y())

    @property
    def ann_id(self) -> str:
        return self._ann_id

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self._apply_style()
            self.update()

    def _apply_style(self) -> None:
        fill = QColor(self._color)
        fill.setAlpha(50 if self._selected else 20)
        self.setBrush(QBrush(fill))
        pen = QPen(self._color)
        pen.setCosmetic(True)
        pen.setWidth(2 if self._selected else 1)
        self.setPen(pen)
