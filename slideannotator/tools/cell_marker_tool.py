from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from .base_tool import BaseTool
from .shift_select_mixin import ShiftSelectMixin


class CellMarkerTool(ShiftSelectMixin, BaseTool):
    def __init__(self, scene, store, view) -> None:
        super().__init__(scene, store)
        self._view = view
        self._sx_init()

    def deactivate(self) -> None:
        self._sx_deactivate()

    # ------------------------------------------------------------------
    def mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        if self._sx_mouse_press(event, scene_pos):
            return
        self._store.add_marker(scene_pos.x(), scene_pos.y(), self.active_channel)

    def mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        self._sx_mouse_move(event, scene_pos)

    def mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        self._sx_mouse_release(event, scene_pos)

    def key_press(self, event: QKeyEvent) -> None:
        self._sx_key_press(event)
