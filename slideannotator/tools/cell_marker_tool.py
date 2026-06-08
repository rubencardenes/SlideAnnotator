from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtGui import QMouseEvent

from .base_tool import BaseTool


class CellMarkerTool(BaseTool):
    def mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        self._store.add_marker(scene_pos.x(), scene_pos.y(), self.active_channel)
