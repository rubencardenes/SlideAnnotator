from __future__ import annotations

import json
from pathlib import Path

from .models import AnnotationStore, CellMarker, FOVAnnotation, RegionAnnotation

_VERSION = "1.0"
_BOX_HALF = 10  # cell marker → bounding box half-size (20px total)


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
    for f in store.fovs.values():
        data["annotations"].append(
            {"id": f.id, "type": "fov", "x": f.x, "y": f.y, "w": f.w, "h": f.h}
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
        elif t == "fov":
            f = FOVAnnotation(
                id=item["id"],
                x=float(item["x"]),
                y=float(item["y"]),
                w=float(item.get("w", 512.0)),
                h=float(item.get("h", 512.0)),
            )
            store._fovs[f.id] = f
            store.annotation_added.emit(f.id)
    store.is_dirty = False


def export_markers_txt(txt_path: Path, slide_path: Path, store: AnnotationStore) -> None:
    """Export cell markers inside each FOV to a text file.

    Format per line:  image_name_x_y: xmin,ymin,xmax,ymax xmin,ymin,xmax,ymax ...
    Only FOVs that contain at least one marker are written.
    """
    image_name = slide_path.stem
    lines: list[str] = []

    for fov in store.fovs.values():
        fx1, fy1 = fov.x, fov.y
        fx2, fy2 = fov.x + fov.w, fov.y + fov.h

        boxes: list[str] = []
        for m in store.markers.values():
            if fx1 <= m.x <= fx2 and fy1 <= m.y <= fy2:
                bx1 = int(round(m.x - _BOX_HALF))
                by1 = int(round(m.y - _BOX_HALF))
                bx2 = int(round(m.x + _BOX_HALF))
                by2 = int(round(m.y + _BOX_HALF))
                boxes.append(f"{bx1},{by1},{bx2},{by2}")

        if boxes:
            key = f"{image_name}_{int(round(fov.x))}_{int(round(fov.y))}"
            lines.append(f"{key}: {' '.join(boxes)}")

    txt_path.write_text("\n".join(lines) + ("\n" if lines else ""))
