from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from ..graphics.cell_marker_item import HALO_EXTRA, SCREEN_RADIUS, CellMarkerItem
from ..graphics.fov_item import FOVItem
from ..graphics.region_item import RegionItem
from .base_tool import BaseTool


class SelectTool(BaseTool):
    def __init__(self, scene, store, view) -> None:
        super().__init__(scene, store)
        self._view = view
        self._dragging = False
        self._drag_id: str | None = None
        self._drag_type: str | None = None  # "marker" or "fov"
        self._drag_start: QPointF | None = None
        self._original_pos: tuple[float, float] | None = None

    def deactivate(self) -> None:
        self._dragging = False
        self._drag_id = None
        self._drag_type = None
        self._store.set_selected(set())

    # ------------------------------------------------------------------
    def mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        hit = self._hit_test(scene_pos)

        if hit is None:
            if not shift:
                self._store.set_selected(set())
            return

        ann_id = hit
        if shift:
            self._store.toggle_selected(ann_id)
        else:
            if ann_id not in self._store.selected:
                self._store.set_selected({ann_id})

        marker = self._store.get_marker(ann_id)
        if marker is not None:
            self._dragging = True
            self._drag_id = ann_id
            self._drag_type = "marker"
            self._drag_start = QPointF(scene_pos)
            self._original_pos = (marker.x, marker.y)
            return

        fov = self._store.get_fov(ann_id)
        if fov is not None:
            self._dragging = True
            self._drag_id = ann_id
            self._drag_type = "fov"
            self._drag_start = QPointF(scene_pos)
            self._original_pos = (fov.x, fov.y)

    def mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        if not self._dragging or self._drag_id is None:
            return
        delta = scene_pos - self._drag_start
        ox, oy = self._original_pos
        if self._drag_type == "marker":
            self._store.move_marker(self._drag_id, ox + delta.x(), oy + delta.y())
        elif self._drag_type == "fov":
            self._store.move_fov(self._drag_id, ox + delta.x(), oy + delta.y())

    def mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        if self._dragging and self._drag_id is not None and self._original_pos is not None:
            self._store.record_move(self._drag_id, self._drag_type, *self._original_pos)
        self._dragging = False
        self._drag_id = None
        self._drag_type = None
        self._original_pos = None

    def key_press(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_D, Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._store.delete_batch(list(self._store.selected))

    # ------------------------------------------------------------------
    def _hit_test(self, scene_pos: QPointF) -> str | None:
        # For markers: proximity check in screen space (shape() uses a huge
        # bounding circle so shape-intersection always hits every marker).
        scale = self._view.transform().m11()  # scene units → pixels
        hit_radius_sq = ((SCREEN_RADIUS + HALO_EXTRA) / max(scale, 1e-9)) ** 2

        best_id: str | None = None
        best_dist_sq = float("inf")
        for item in self._scene.items():
            if isinstance(item, CellMarkerItem):
                p = item.pos()
                dx = p.x() - scene_pos.x()
                dy = p.y() - scene_pos.y()
                d2 = dx * dx + dy * dy
                if d2 <= hit_radius_sq and d2 < best_dist_sq:
                    best_dist_sq = d2
                    best_id = item.ann_id
        if best_id is not None:
            return best_id

        # For regions and FOVs: shape-based intersection is fine
        vt = self._view.viewport_transform()
        items = self._scene.items(
            scene_pos,
            Qt.ItemSelectionMode.IntersectsItemShape,
            Qt.SortOrder.DescendingOrder,
            vt,
        )
        for item in items:
            if isinstance(item, (RegionItem, FOVItem)):
                return item.ann_id
        return None
