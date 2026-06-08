from __future__ import annotations

from PySide6.QtWidgets import QGraphicsPixmapItem
from PySide6.QtCore import QRectF


class TileItem(QGraphicsPixmapItem):
    """A single composited tile placed in scene (level-0) coordinates."""

    def __init__(self, scene_x: float, scene_y: float, scale: float) -> None:
        super().__init__()
        self.setPos(scene_x, scene_y)
        self.setScale(scale)
        self.setZValue(-1)
