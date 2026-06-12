from __future__ import annotations

import getpass
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Signal

MARKER_BOX_HALF = 10  # half-side of the bounding box saved in txt export (scene pixels)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _current_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


@dataclass
class CellMarker:
    id: str
    x: float
    y: float
    channel: str
    w: float = 10.0
    h: float = 10.0
    color: tuple[int, int, int] = field(default_factory=lambda: (255, 255, 255))
    created_at: str = field(default_factory=_now_iso)
    modified_at: str = field(default_factory=_now_iso)
    created_by: str = field(default_factory=_current_user)
    slide_name: str = ""
    type: str = "cell_marker"

    @staticmethod
    def create(
        x: float, y: float, channel: str, w: float = 10.0, h: float = 10.0
    ) -> CellMarker:
        return CellMarker(id=str(uuid.uuid4()), x=x, y=y, channel=channel, w=w, h=h)


@dataclass
class RegionAnnotation:
    id: str
    points: list[tuple[float, float]]
    channel: str
    color: tuple[int, int, int] = field(default_factory=lambda: (255, 255, 255))
    created_at: str = field(default_factory=_now_iso)
    modified_at: str = field(default_factory=_now_iso)
    created_by: str = field(default_factory=_current_user)
    slide_name: str = ""
    type: str = "region"

    @staticmethod
    def create(
        points: list[tuple[float, float]], channel: str
    ) -> RegionAnnotation:
        return RegionAnnotation(
            id=str(uuid.uuid4()), points=list(points), channel=channel
        )


@dataclass
class FOVAnnotation:
    id: str
    x: float  # top-left x
    y: float  # top-left y
    w: float = 512.0
    h: float = 512.0
    color: tuple[int, int, int] = field(default_factory=lambda: (255, 255, 255))
    created_at: str = field(default_factory=_now_iso)
    modified_at: str = field(default_factory=_now_iso)
    created_by: str = field(default_factory=_current_user)
    slide_name: str = ""
    type: str = "fov"

    @staticmethod
    def create(x: float, y: float, w: float = 512.0, h: float = 512.0) -> FOVAnnotation:
        return FOVAnnotation(id=str(uuid.uuid4()), x=x, y=y, w=w, h=h)


def _snapshot_ann(ann: CellMarker | RegionAnnotation | FOVAnnotation):
    """Return a copy of an annotation for undo history."""
    if isinstance(ann, RegionAnnotation):
        return replace(ann, points=list(ann.points))
    return replace(ann)


class AnnotationStore(QObject):
    annotation_added = Signal(str)      # id
    annotation_removed = Signal(str)    # id
    annotation_moved = Signal(str)      # id (cell markers only)
    selection_changed = Signal(object)  # set[str]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._markers: dict[str, CellMarker] = {}
        self._regions: dict[str, RegionAnnotation] = {}
        self._fovs: dict[str, FOVAnnotation] = {}
        self._selected: set[str] = set()
        self.is_dirty = False
        self._undo_stack: list = []
        self._redo_stack: list = []
        self._is_undoing = False

    # ------------------------------------------------------------------
    def add_marker(self, x: float, y: float, channel: str) -> CellMarker:
        m = CellMarker.create(x, y, channel)
        self._markers[m.id] = m
        self.is_dirty = True
        self.annotation_added.emit(m.id)
        if not self._is_undoing:
            snap = _snapshot_ann(m)
            self._push_undo(lambda aid=m.id: self.delete(aid), lambda s=snap: self._restore(s))
        return m

    def add_region(
        self, points: list[tuple[float, float]], channel: str
    ) -> RegionAnnotation:
        r = RegionAnnotation.create(points, channel)
        self._regions[r.id] = r
        self.is_dirty = True
        self.annotation_added.emit(r.id)
        if not self._is_undoing:
            snap = _snapshot_ann(r)
            self._push_undo(lambda aid=r.id: self.delete(aid), lambda s=snap: self._restore(s))
        return r

    def add_fov(
        self, cx: float, cy: float, w: float = 512.0, h: float = 512.0
    ) -> FOVAnnotation:
        # cx, cy is the center; stored x,y is top-left
        f = FOVAnnotation.create(cx - w / 2, cy - h / 2, w, h)
        self._fovs[f.id] = f
        self.is_dirty = True
        self.annotation_added.emit(f.id)
        if not self._is_undoing:
            snap = _snapshot_ann(f)
            self._push_undo(lambda aid=f.id: self.delete(aid), lambda s=snap: self._restore(s))
        return f

    def delete(self, ann_id: str) -> None:
        ann = self.get_annotation(ann_id)
        self._markers.pop(ann_id, None)
        self._regions.pop(ann_id, None)
        self._fovs.pop(ann_id, None)
        self._selected.discard(ann_id)
        self.is_dirty = True
        self.annotation_removed.emit(ann_id)
        if ann is not None and not self._is_undoing:
            snap = _snapshot_ann(ann)
            self._push_undo(lambda s=snap: self._restore(s), lambda aid=ann_id: self.delete(aid))

    def move_marker(self, ann_id: str, x: float, y: float) -> None:
        if ann_id in self._markers:
            self._markers[ann_id].x = x
            self._markers[ann_id].y = y
            self.is_dirty = True
            self.annotation_moved.emit(ann_id)

    def set_selected(self, ids: set[str]) -> None:
        if ids != self._selected:
            self._selected = set(ids)
            self.selection_changed.emit(self._selected)

    def toggle_selected(self, ann_id: str) -> None:
        new_sel = set(self._selected)
        if ann_id in new_sel:
            new_sel.discard(ann_id)
        else:
            new_sel.add(ann_id)
        self.set_selected(new_sel)

    def get_annotation(self, ann_id: str) -> CellMarker | RegionAnnotation | FOVAnnotation | None:
        return self._markers.get(ann_id) or self._regions.get(ann_id) or self._fovs.get(ann_id)

    def get_marker(self, ann_id: str) -> CellMarker | None:
        return self._markers.get(ann_id)

    def get_fov(self, ann_id: str) -> FOVAnnotation | None:
        return self._fovs.get(ann_id)

    def get_region(self, ann_id: str) -> RegionAnnotation | None:
        return self._regions.get(ann_id)

    def set_region_points(self, ann_id: str, points: list[tuple[float, float]]) -> None:
        if ann_id in self._regions:
            self._regions[ann_id].points = list(points)
            self.is_dirty = True
            self.annotation_moved.emit(ann_id)

    def move_fov(self, ann_id: str, x: float, y: float) -> None:
        if ann_id in self._fovs:
            self._fovs[ann_id].x = x
            self._fovs[ann_id].y = y
            self.is_dirty = True
            self.annotation_moved.emit(ann_id)

    def set_dirty(self, value: bool) -> None:
        self.is_dirty = value

    @property
    def selected(self) -> set[str]:
        return set(self._selected)

    @property
    def markers(self) -> dict[str, CellMarker]:
        return self._markers

    @property
    def regions(self) -> dict[str, RegionAnnotation]:
        return self._regions

    @property
    def fovs(self) -> dict[str, FOVAnnotation]:
        return self._fovs

    def clear(self) -> None:
        self._is_undoing = True
        try:
            for ann_id in list(self._markers) + list(self._regions) + list(self._fovs):
                self.delete(ann_id)
        finally:
            self._is_undoing = False
        self._undo_stack.clear()
        self._redo_stack.clear()

    def all_annotations(self) -> list[CellMarker | RegionAnnotation | FOVAnnotation]:
        return list(self._markers.values()) + list(self._regions.values()) + list(self._fovs.values())

    # ------------------------------------------------------------------
    # Undo / Redo

    def add_region_batch(
        self, regions_data: list[tuple[list[tuple[float, float]], str]]
    ) -> list[RegionAnnotation]:
        """Add multiple regions as a single undoable action."""
        if not regions_data:
            return []
        regions: list[RegionAnnotation] = []
        self._is_undoing = True
        try:
            for points, channel in regions_data:
                r = RegionAnnotation.create(points, channel)
                self._regions[r.id] = r
                self.is_dirty = True
                self.annotation_added.emit(r.id)
                regions.append(r)
        finally:
            self._is_undoing = False
        snapshots = [_snapshot_ann(r) for r in regions]
        ids = [r.id for r in regions]
        self._push_undo(
            lambda iids=ids: [self.delete(aid) for aid in iids],
            lambda ss=snapshots: [self._restore(s) for s in ss],
        )
        return regions

    def add_marker_batch(
        self, markers_data: list[tuple[float, float, str, float, float]]
    ) -> list[CellMarker]:
        """Add multiple markers as a single undoable action (x, y, channel, w, h)."""
        if not markers_data:
            return []
        markers: list[CellMarker] = []
        self._is_undoing = True
        try:
            for x, y, channel, w, h in markers_data:
                m = CellMarker.create(x, y, channel, w, h)
                self._markers[m.id] = m
                self.is_dirty = True
                self.annotation_added.emit(m.id)
                markers.append(m)
        finally:
            self._is_undoing = False
        snapshots = [_snapshot_ann(m) for m in markers]
        ids = [m.id for m in markers]
        self._push_undo(
            lambda iids=ids: [self.delete(aid) for aid in iids],
            lambda ss=snapshots: [self._restore(s) for s in ss],
        )
        return markers

    def delete_batch(self, ann_ids: list[str]) -> None:
        """Delete multiple annotations as a single undoable action."""
        if self._is_undoing:
            return
        anns = [self.get_annotation(aid) for aid in ann_ids if self.get_annotation(aid) is not None]
        if not anns:
            return
        snapshots = [_snapshot_ann(a) for a in anns]
        clean_ids = [a.id for a in anns]
        self._is_undoing = True
        try:
            for aid in clean_ids:
                self.delete(aid)
        finally:
            self._is_undoing = False
        self._push_undo(
            lambda ss=snapshots: [self._restore(s) for s in ss],
            lambda ids=clean_ids: [self.delete(aid) for aid in ids],
        )

    def record_move(self, ann_id: str, kind: str, old_x: float, old_y: float) -> None:
        """Record a completed single-annotation drag for undo."""
        if self._is_undoing:
            return
        ann = self._markers.get(ann_id) if kind == "marker" else self._fovs.get(ann_id)
        if ann is None or (ann.x == old_x and ann.y == old_y):
            return
        new_x, new_y = ann.x, ann.y
        self._push_undo(
            lambda aid=ann_id, k=kind, x=old_x, y=old_y: self._apply_move(aid, (k, x, y)),
            lambda aid=ann_id, k=kind, x=new_x, y=new_y: self._apply_move(aid, (k, x, y)),
        )

    def record_batch_move(self, originals: dict) -> None:
        """Record a completed multi-annotation drag for undo."""
        if self._is_undoing or not originals:
            return
        new_state: dict = {}
        for ann_id, orig in originals.items():
            kind = orig[0]
            if kind == "marker":
                ann = self._markers.get(ann_id)
                if ann is not None:
                    new_state[ann_id] = ("marker", ann.x, ann.y)
            elif kind == "fov":
                ann = self._fovs.get(ann_id)
                if ann is not None:
                    new_state[ann_id] = ("fov", ann.x, ann.y)
            elif kind == "region":
                ann = self._regions.get(ann_id)
                if ann is not None:
                    new_state[ann_id] = ("region", list(ann.points))
        if not new_state:
            return
        if not any(originals.get(aid) != new_state.get(aid) for aid in new_state):
            return
        self._push_undo(
            lambda old=dict(originals): [self._apply_move(aid, state) for aid, state in old.items()],
            lambda new=new_state: [self._apply_move(aid, state) for aid, state in new.items()],
        )

    def undo(self) -> None:
        if not self._undo_stack:
            return
        undo_fn, redo_fn = self._undo_stack.pop()
        self._is_undoing = True
        try:
            undo_fn()
        finally:
            self._is_undoing = False
        self._redo_stack.append((undo_fn, redo_fn))

    def redo(self) -> None:
        if not self._redo_stack:
            return
        undo_fn, redo_fn = self._redo_stack.pop()
        self._is_undoing = True
        try:
            redo_fn()
        finally:
            self._is_undoing = False
        self._undo_stack.append((undo_fn, redo_fn))

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def _push_undo(self, undo_fn, redo_fn) -> None:
        self._undo_stack.append((undo_fn, redo_fn))
        self._redo_stack.clear()

    def _restore(self, ann) -> None:
        if isinstance(ann, CellMarker):
            self._markers[ann.id] = ann
        elif isinstance(ann, RegionAnnotation):
            self._regions[ann.id] = ann
        elif isinstance(ann, FOVAnnotation):
            self._fovs[ann.id] = ann
        self.is_dirty = True
        self.annotation_added.emit(ann.id)

    def _load_annotation(self, ann: CellMarker | RegionAnnotation | FOVAnnotation) -> None:
        """Insert a pre-built annotation (used by deserialization; bypasses undo stack)."""
        if isinstance(ann, CellMarker):
            self._markers[ann.id] = ann
        elif isinstance(ann, RegionAnnotation):
            self._regions[ann.id] = ann
        elif isinstance(ann, FOVAnnotation):
            self._fovs[ann.id] = ann
        self.annotation_added.emit(ann.id)

    def _apply_move(self, ann_id: str, state: tuple) -> None:
        kind = state[0]
        if kind == "marker":
            self.move_marker(ann_id, state[1], state[2])
        elif kind == "fov":
            self.move_fov(ann_id, state[1], state[2])
        elif kind == "region":
            self.set_region_points(ann_id, state[1])
