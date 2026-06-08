from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal


@dataclass
class CellMarker:
    id: str
    x: float
    y: float
    channel: str
    type: str = "cell_marker"

    @staticmethod
    def create(x: float, y: float, channel: str) -> "CellMarker":
        return CellMarker(id=str(uuid.uuid4()), x=x, y=y, channel=channel)


@dataclass
class RegionAnnotation:
    id: str
    points: list[tuple[float, float]]
    channel: str
    type: str = "region"

    @staticmethod
    def create(
        points: list[tuple[float, float]], channel: str
    ) -> "RegionAnnotation":
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
    type: str = "fov"

    @staticmethod
    def create(x: float, y: float, w: float = 512.0, h: float = 512.0) -> "FOVAnnotation":
        return FOVAnnotation(id=str(uuid.uuid4()), x=x, y=y, w=w, h=h)


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

    # ------------------------------------------------------------------
    def add_marker(self, x: float, y: float, channel: str) -> CellMarker:
        m = CellMarker.create(x, y, channel)
        self._markers[m.id] = m
        self.is_dirty = True
        self.annotation_added.emit(m.id)
        return m

    def add_region(
        self, points: list[tuple[float, float]], channel: str
    ) -> RegionAnnotation:
        r = RegionAnnotation.create(points, channel)
        self._regions[r.id] = r
        self.is_dirty = True
        self.annotation_added.emit(r.id)
        return r

    def add_fov(
        self, cx: float, cy: float, w: float = 512.0, h: float = 512.0
    ) -> FOVAnnotation:
        # cx, cy is the center; stored x,y is top-left
        f = FOVAnnotation.create(cx - w / 2, cy - h / 2, w, h)
        self._fovs[f.id] = f
        self.is_dirty = True
        self.annotation_added.emit(f.id)
        return f

    def delete(self, ann_id: str) -> None:
        self._markers.pop(ann_id, None)
        self._regions.pop(ann_id, None)
        self._fovs.pop(ann_id, None)
        self._selected.discard(ann_id)
        self.is_dirty = True
        self.annotation_removed.emit(ann_id)

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

    def all_annotations(self) -> list[CellMarker | RegionAnnotation | FOVAnnotation]:
        return list(self._markers.values()) + list(self._regions.values()) + list(self._fovs.values())
