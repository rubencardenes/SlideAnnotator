from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QKeyEvent, QMouseEvent, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsPolygonItem

from .base_tool import BaseTool
from .shift_select_mixin import ShiftSelectMixin

MIN_SCREEN_PX = 3.0


class RegionTool(ShiftSelectMixin, BaseTool):
    def __init__(self, scene, store, view) -> None:
        super().__init__(scene, store)
        self._view = view
        self._points: list[QPointF] = []
        self._preview: QGraphicsPolygonItem | None = None
        self._drawing = False
        self._sx_init()

    def activate(self) -> None:
        self._cancel()

    def deactivate(self) -> None:
        self._cancel()
        self._sx_deactivate()

    # ------------------------------------------------------------------
    def mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        if self._sx_mouse_press(event, scene_pos):
            return
        if not self._drawing:
            self._drawing = True
            self._points = [QPointF(scene_pos)]
            self._preview = QGraphicsPolygonItem()
            pen = QPen(QColor(255, 200, 0))
            pen.setCosmetic(True)
            pen.setWidth(2)
            self._preview.setPen(pen)
            self._preview.setBrush(QBrush(QColor(255, 200, 0, 40)))
            self._preview.setZValue(20)
            self._scene.addItem(self._preview)

    def mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        if self._sx_mouse_move(event, scene_pos):
            return
        if not self._drawing:
            return
        zoom = self._view.current_zoom()
        if zoom < 1e-9:
            return
        if self._points:
            last = self._points[-1]
            dx = (scene_pos.x() - last.x()) * zoom
            dy = (scene_pos.y() - last.y()) * zoom
            if math.hypot(dx, dy) >= MIN_SCREEN_PX:
                self._points.append(QPointF(scene_pos))
                self._update_preview()

    def mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        if self._sx_mouse_release(event, scene_pos):
            return
        if not self._drawing:
            return
        if len(self._points) >= 3:
            pts = [(p.x(), p.y()) for p in self._points]
            self._store.add_region(pts, self.active_channel)
        self._cancel()

    def key_press(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._sx_cancel()
            self._cancel()
            return
        if self._sx_key_press(event):
            return

    # ------------------------------------------------------------------
    def _update_preview(self) -> None:
        if self._preview and self._points:
            poly = QPolygonF(self._points)
            self._preview.setPolygon(poly)

    def _cancel(self) -> None:
        self._drawing = False
        self._points.clear()
        if self._preview is not None:
            self._scene.removeItem(self._preview)
            self._preview = None
