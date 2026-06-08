from __future__ import annotations

import json
from pathlib import Path

from .models import AnnotationStore, CellMarker, RegionAnnotation

_VERSION = "1.0"


def save_annotations(
    ann_path: Path, slide_path: Path, store: AnnotationStore
) -> None:
    data = {
        "version": _VERSION,
        "slide": str(slide_path),
        "annotations": [],
    }
    for m in store.markers.values():
        data["annotations"].append(
            {"id": m.id, "type": "cell_marker", "x": m.x, "y": m.y, "channel": m.channel}
        )
    for r in store.regions.values():
        data["annotations"].append(
            {"id": r.id, "type": "region", "points": r.points, "channel": r.channel}
        )
    ann_path.write_text(json.dumps(data, indent=2))


def load_annotations(ann_path: Path, store: AnnotationStore) -> None:
    raw = json.loads(ann_path.read_text())
    for item in raw.get("annotations", []):
        t = item.get("type")
        if t == "cell_marker":
            m = CellMarker(
                id=item["id"],
                x=float(item["x"]),
                y=float(item["y"]),
                channel=item.get("channel", ""),
            )
            store._markers[m.id] = m
            store.annotation_added.emit(m.id)
        elif t == "region":
            r = RegionAnnotation(
                id=item["id"],
                points=[tuple(p) for p in item["points"]],
                channel=item.get("channel", ""),
            )
            store._regions[r.id] = r
            store.annotation_added.emit(r.id)
    store.is_dirty = False
