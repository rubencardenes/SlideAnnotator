from __future__ import annotations

from abc import ABC, abstractmethod

from PySide6.QtCore import QPointF
from PySide6.QtGui import QKeyEvent, QMouseEvent


class BaseTool(ABC):
    is_pan: bool = False

    def __init__(self, scene, store) -> None:
        self._scene = scene
        self._store = store
        self.active_channel: str = ""

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass

    def mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        pass

    def mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        pass

    def mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        pass

    def key_press(self, event: QKeyEvent) -> None:
        pass
