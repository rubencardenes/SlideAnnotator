from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsRectItem

from ..graphics.cell_marker_item import HALO_EXTRA, SCREEN_RADIUS, CellMarkerItem
from ..graphics.fov_item import FOVItem
from ..graphics.region_item import RegionItem


class ShiftSelectMixin:
    """Adds Shift-based selection/move/rubber-band/delete to annotation tools.

    Requires the host class to have: self._scene, self._store, self._view.
    Call _sx_init() from __init__ and _sx_deactivate() from deactivate().
    In mouse_press/move/release/key_press delegate to _sx_* first; if the
    method returns True the event was consumed and normal tool logic should
    be skipped.
    """

    def _sx_init(self) -> None:
        self._sx_mode: str | None = None  # "pre_drag" | "dragging" | "rubber_banding"
        self._sx_drag_start: QPointF | None = None
        self._sx_hit_id: str | None = None
        self._sx_was_selected: bool = False
        self._sx_moved: bool = False
        self._sx_drag_originals: dict = {}
        self._sx_rubber_item: QGraphicsRectItem | None = None

    def _sx_deactivate(self) -> None:
        self._sx_cancel()
        self._store.set_selected(set())

    def _sx_cancel(self) -> None:
        if self._sx_rubber_item is not None:
            self._scene.removeItem(self._sx_rubber_item)
            self._sx_rubber_item = None
        self._sx_mode = None
        self._sx_drag_start = None
        self._sx_drag_originals = {}
        self._sx_hit_id = None
        self._sx_was_selected = False
        self._sx_moved = False

    # ------------------------------------------------------------------
    def _sx_mouse_press(self, event, scene_pos: QPointF) -> bool:
        if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            return False

        hit = self._sx_hit_test(scene_pos)
        self._sx_drag_start = QPointF(scene_pos)
        self._sx_hit_id = hit
        self._sx_moved = False

        if hit is not None:
            self._sx_was_selected = hit in self._store.selected
            if not self._sx_was_selected:
                new_sel = set(self._store.selected)
                new_sel.add(hit)
                self._store.set_selected(new_sel)
            self._sx_drag_originals = self._sx_get_originals(self._store.selected)
            self._sx_mode = "pre_drag"
        else:
            self._sx_was_selected = False
            self._sx_mode = "rubber_banding"
            self._sx_rubber_item = QGraphicsRectItem(QRectF(scene_pos.x(), scene_pos.y(), 0, 0))
            pen = QPen(QColor(100, 180, 255))
            pen.setCosmetic(True)
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setWidth(1)
            self._sx_rubber_item.setPen(pen)
            self._sx_rubber_item.setBrush(QBrush(QColor(100, 180, 255, 20)))
            self._sx_rubber_item.setZValue(100)
            self._scene.addItem(self._sx_rubber_item)

        return True

    def _sx_mouse_move(self, event, scene_pos: QPointF) -> bool:
        if self._sx_mode is None:
            return False

        if self._sx_mode in ("pre_drag", "dragging"):
            delta = scene_pos - self._sx_drag_start
            zoom = self._view.transform().m11()
            moved_px = (delta.x() ** 2 + delta.y() ** 2) ** 0.5 * zoom
            if moved_px > 3.0:
                self._sx_mode = "dragging"
                self._sx_moved = True
                for ann_id, orig in self._sx_drag_originals.items():
                    self._sx_apply_move(ann_id, orig, delta)
            return True

        if self._sx_mode == "rubber_banding":
            if self._sx_rubber_item is not None:
                sx = min(self._sx_drag_start.x(), scene_pos.x())
                sy = min(self._sx_drag_start.y(), scene_pos.y())
                ex = max(self._sx_drag_start.x(), scene_pos.x())
                ey = max(self._sx_drag_start.y(), scene_pos.y())
                self._sx_rubber_item.setRect(QRectF(sx, sy, ex - sx, ey - sy))
            return True

        return False

    def _sx_mouse_release(self, event, scene_pos: QPointF) -> bool:
        if self._sx_mode is None:
            return False

        if self._sx_mode == "rubber_banding":
            if self._sx_rubber_item is not None:
                rect = self._sx_rubber_item.rect()
                if rect.width() > 0 or rect.height() > 0:
                    self._sx_select_in_rect(rect)
            self._sx_cancel()
            return True

        if self._sx_mode in ("pre_drag", "dragging"):
            if self._sx_moved and self._sx_drag_originals:
                self._store.record_batch_move(self._sx_drag_originals)
            if not self._sx_moved and self._sx_hit_id is not None and self._sx_was_selected:
                # No movement — treat as a toggle-off click on an already-selected item
                self._store.toggle_selected(self._sx_hit_id)
            self._sx_cancel()
            return True

        return False

    def _sx_key_press(self, event) -> bool:
        if event.key() in (Qt.Key.Key_D, Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._store.delete_batch(list(self._store.selected))
            return True
        return False

    # ------------------------------------------------------------------
    def _sx_hit_test(self, scene_pos: QPointF) -> str | None:
        # Markers: proximity check in screen space (shape() is a huge circle)
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
        # Regions and FOVs: shape-based intersection
        vt = self._view.viewport_transform()
        for item in self._scene.items(
            scene_pos,
            Qt.ItemSelectionMode.IntersectsItemShape,
            Qt.SortOrder.DescendingOrder,
            vt,
        ):
            if isinstance(item, (RegionItem, FOVItem)):
                return item.ann_id
        return None

    def _sx_select_in_rect(self, rect: QRectF) -> None:
        new_sel = set(self._store.selected)
        # Markers: use center-point containment (shape() is a huge circle)
        for item in self._scene.items():
            if isinstance(item, CellMarkerItem) and rect.contains(item.pos()):
                new_sel.add(item.ann_id)
        # Regions and FOVs: shape-based intersection is fine
        vt = self._view.viewport_transform()
        for item in self._scene.items(
            rect,
            Qt.ItemSelectionMode.IntersectsItemShape,
            Qt.SortOrder.DescendingOrder,
            vt,
        ):
            if isinstance(item, (RegionItem, FOVItem)):
                new_sel.add(item.ann_id)
        self._store.set_selected(new_sel)

    def _sx_get_originals(self, ids: set[str]) -> dict:
        originals = {}
        for ann_id in ids:
            m = self._store.get_marker(ann_id)
            if m is not None:
                originals[ann_id] = ("marker", m.x, m.y)
                continue
            f = self._store.get_fov(ann_id)
            if f is not None:
                originals[ann_id] = ("fov", f.x, f.y)
                continue
            r = self._store.get_region(ann_id)
            if r is not None:
                originals[ann_id] = ("region", list(r.points))
        return originals

    def _sx_apply_move(self, ann_id: str, orig: tuple, delta: QPointF) -> None:
        kind = orig[0]
        if kind == "marker":
            self._store.move_marker(ann_id, orig[1] + delta.x(), orig[2] + delta.y())
        elif kind == "fov":
            self._store.move_fov(ann_id, orig[1] + delta.x(), orig[2] + delta.y())
        elif kind == "region":
            new_pts = [(x + delta.x(), y + delta.y()) for x, y in orig[1]]
            self._store.set_region_points(ann_id, new_pts)
