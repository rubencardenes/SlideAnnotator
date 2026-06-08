from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent

from ..graphics.cell_marker_item import CellMarkerItem, HALO_EXTRA, SCREEN_RADIUS
from ..graphics.region_item import RegionItem
from .base_tool import BaseTool


class CellMarkerTool(BaseTool):
    def __init__(self, scene, store, view) -> None:
        super().__init__(scene, store)
        self._view = view

    def mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            hit = self._hit_test(scene_pos)
            if hit is not None:
                self._store.toggle_selected(hit)
            return
        self._store.add_marker(scene_pos.x(), scene_pos.y(), self.active_channel)

    def _hit_test(self, scene_pos: QPointF) -> str | None:
        scale = self._view.transform().m11()
        hit_r2 = ((SCREEN_RADIUS + HALO_EXTRA) / max(scale, 1e-9)) ** 2
        best_id, best_d2 = None, float("inf")
        for item in self._scene.items():
            if isinstance(item, CellMarkerItem):
                p = item.pos()
                d2 = (p.x() - scene_pos.x()) ** 2 + (p.y() - scene_pos.y()) ** 2
                if d2 <= hit_r2 and d2 < best_d2:
                    best_d2, best_id = d2, item.ann_id
        if best_id is not None:
            return best_id
        vt = self._view.viewport_transform()
        for item in self._scene.items(
            scene_pos,
            Qt.ItemSelectionMode.IntersectsItemShape,
            Qt.SortOrder.DescendingOrder,
            vt,
        ):
            if isinstance(item, RegionItem):
                return item.ann_id
        return None
