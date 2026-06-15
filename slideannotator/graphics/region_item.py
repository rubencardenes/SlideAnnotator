from __future__ import annotations

from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsPolygonItem


class RegionItem(QGraphicsPolygonItem):
    """Closed polygon region annotation."""

    def __init__(self, ann_id: str, color: QColor, fill_opacity: float = 40 / 255) -> None:
        super().__init__()
        self._ann_id = ann_id
        self._color = color
        self._selected = False
        self._fill_opacity = max(0.0, min(1.0, fill_opacity))
        self._apply_style()
        self.setZValue(9)

    @property
    def ann_id(self) -> str:
        return self._ann_id

    def set_fill_opacity(self, opacity: float) -> None:
        self._fill_opacity = max(0.0, min(1.0, opacity))
        self._apply_style()
        self.update()

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self._apply_style()
            self.update()

    def _apply_style(self) -> None:
        base = int(self._fill_opacity * 255)
        alpha = min(base * 2, 255) if self._selected else base
        fill = QColor(self._color.red(), self._color.green(), self._color.blue(), alpha)
        self.setBrush(QBrush(fill))
        pen_width = 2 if self._selected else 1
        pen_color = QColor(255, 255, 255) if self._selected else self._color
        # Cosmetic pen = always 1-2 pixels regardless of zoom
        pen = QPen(pen_color, 0)
        pen.setCosmetic(True)
        pen.setWidth(pen_width)
        self.setPen(pen)
