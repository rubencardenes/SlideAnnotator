from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .models import MARKER_BOX_HALF, AnnotationStore


def needs_cell_marker_fovs(output_dir: Path, slide_name: str, store: AnnotationStore) -> bool:
    """Return True if any expected cell-marker FOV image is missing from disk."""
    fovs_dir = output_dir / "Cell Marker Annotations" / "FOVs"
    for channel in {m.channel for m in store.markers.values()}:
        for fov in store.fovs.values():
            has_marker = any(
                m.channel == channel
                and fov.x <= m.x <= fov.x + fov.w
                and fov.y <= m.y <= fov.y + fov.h
                for m in store.markers.values()
            )
            if has_marker:
                path = (
                    fovs_dir / f"{slide_name}_{channel}_{int(round(fov.x))}_{int(round(fov.y))}.png"
                )
                if not path.exists():
                    return True
    return False


def needs_region_fovs(output_dir: Path, slide_name: str, store: AnnotationStore) -> bool:
    """Return True if any expected region FOV image is missing from disk."""
    fovs_dir = output_dir / "Region Annotations" / "FOVs"
    channels = {r.channel for r in store.regions.values() if r.points}
    for channel in channels:
        for fov in store.fovs.values():
            if fov.channel != channel:
                continue
            path = fovs_dir / f"{slide_name}_{channel}_{int(round(fov.x))}_{int(round(fov.y))}.png"
            if not path.exists():
                return True
    return False


def _find_dapi_channel(reader: Any) -> int | None:
    for i, ch in enumerate(reader.channels):
        n = ch.name.lower()
        if "dapi" in n or "hoechst" in n:
            return i
    return None


def _save_fov_rgb16(
    out_path: Path,
    reader: Any,
    annot_ch_idx: int,
    dapi_ch_idx: int | None,
    x: int,
    y: int,
    w: int,
    h: int,
) -> bool:
    """Save a 16-bit RGB PNG: red = annotation channel, green = empty, blue = DAPI/Hoechst."""
    import pyvips

    try:
        raw = reader.read_region(0, x, y, w, h)  # (C, h, w) uint16
        red = raw[annot_ch_idx]
        green = np.zeros((h, w), dtype=np.uint16)
        blue = raw[dapi_ch_idx] if dapi_ch_idx is not None else np.zeros((h, w), dtype=np.uint16)
        rgb = np.ascontiguousarray(np.stack([red, green, blue], axis=2))  # (h, w, 3) uint16
        vi = pyvips.Image.new_from_memory(rgb.tobytes(), w, h, 3, "ushort")
        vi.write_to_file(str(out_path))
        return True
    except Exception:
        return False


def export_cell_marker_annot(
    output_dir: Path,
    slide_name: str,
    store: AnnotationStore,
    reader: Any | None = None,
    selected_channels: set[str] | None = None,
) -> tuple[int, int]:
    """Export cell marker annotations to 'Cell Marker Annotations' directory.

    Writes per-channel txt files to Annot/ and, when reader is provided, FOV
    images to FOVs/.  Returns (saved_count, error_count).
    When *selected_channels* is provided only those channels are exported.
    """
    stem = slide_name
    annot_dir = output_dir / "Cell Marker Annotations" / "Annot"
    fovs_dir = output_dir / "Cell Marker Annotations" / "FOVs"
    for d in (annot_dir, fovs_dir):
        d.mkdir(parents=True, exist_ok=True)

    ch_index: dict[str, int] = (
        {ch.name: i for i, ch in enumerate(reader.channels)} if reader else {}
    )
    dapi_ch_idx = _find_dapi_channel(reader) if reader else None
    saved = errors = 0

    marker_channels = {m.channel for m in store.markers.values()}
    if selected_channels is not None:
        marker_channels = marker_channels & selected_channels
    for channel in sorted(marker_channels):
        ch_idx = ch_index.get(channel)
        lines: list[str] = []

        for fov in store.fovs.values():
            fx1, fy1 = fov.x, fov.y
            fx2, fy2 = fov.x + fov.w, fov.y + fov.h
            boxes: list[str] = []
            for m in store.markers.values():
                if m.channel != channel:
                    continue
                if fx1 <= m.x <= fx2 and fy1 <= m.y <= fy2:
                    bx1 = int(round(m.x - MARKER_BOX_HALF - fx1))
                    by1 = int(round(m.y - MARKER_BOX_HALF - fy1))
                    bx2 = int(round(m.x + MARKER_BOX_HALF - fx1))
                    by2 = int(round(m.y + MARKER_BOX_HALF - fy1))
                    boxes.append(f"{bx1},{by1},{bx2},{by2}")
            if boxes:
                key = f"{stem}_{int(round(fov.x))}_{int(round(fov.y))}"
                lines.append(f"{key}: {' '.join(boxes)}")
                if reader and ch_idx is not None:
                    fov_path = (
                        fovs_dir / f"{stem}_{channel}_{int(round(fov.x))}_{int(round(fov.y))}.png"
                    )
                    if not fov_path.exists():
                        ok = _save_fov_rgb16(
                            fov_path,
                            reader,
                            ch_idx,
                            dapi_ch_idx,
                            int(fov.x),
                            int(fov.y),
                            int(fov.w),
                            int(fov.h),
                        )
                        saved += ok
                        errors += not ok

        if lines:
            txt_path = annot_dir / f"{stem}_{channel}.txt"
            txt_path.write_text("\n".join(lines) + "\n")
            saved += 1

    return saved, errors


def export_region_annot(
    output_dir: Path,
    slide_name: str,
    store: AnnotationStore,
    reader: Any | None = None,
    selected_channels: set[str] | None = None,
) -> tuple[int, int]:
    """Export region annotations to 'Region Annotations' directory.

    Writes binary masks to Annot/ and, when reader is provided, FOV images to
    FOVs/.  Returns (saved_count, error_count).
    When *selected_channels* is provided only those channels are exported.
    """
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QBrush, QImage, QPainter, QPolygonF

    stem = slide_name
    annot_dir = output_dir / "Region Annotations" / "Annot"
    fovs_dir = output_dir / "Region Annotations" / "FOVs"
    for d in (annot_dir, fovs_dir):
        d.mkdir(parents=True, exist_ok=True)

    ch_index: dict[str, int] = (
        {ch.name: i for i, ch in enumerate(reader.channels)} if reader else {}
    )
    dapi_ch_idx = _find_dapi_channel(reader) if reader else None
    saved = errors = 0

    regions_by_channel: dict[str, list] = {}
    for region in store.regions.values():
        if region.points:
            if selected_channels is None or region.channel in selected_channels:
                regions_by_channel.setdefault(region.channel, []).append(region)

    for channel, channel_regions in sorted(regions_by_channel.items()):
        ch_idx = ch_index.get(channel)

        for fov in store.fovs.values():
            if fov.channel != channel:
                continue
            fx, fy = fov.x, fov.y
            fw, fh = int(fov.w), int(fov.h)
            x_key = int(round(fx))
            y_key = int(round(fy))

            if reader and ch_idx is not None:
                fov_path = fovs_dir / f"{stem}_{channel}_{x_key}_{y_key}.png"
                if not fov_path.exists():
                    ok = _save_fov_rgb16(
                        fov_path, reader, ch_idx, dapi_ch_idx, int(fx), int(fy), fw, fh
                    )
                    saved += ok
                    errors += not ok

            overlapping = [
                r
                for r in channel_regions
                if r.points
                and not (
                    max(p[0] for p in r.points) < fx
                    or min(p[0] for p in r.points) > fx + fw
                    or max(p[1] for p in r.points) < fy
                    or min(p[1] for p in r.points) > fy + fh
                )
            ]
            if not overlapping:
                continue

            mask_path = annot_dir / f"{stem}_{channel}_{x_key}_{y_key}.png"
            try:
                mask_img = QImage(fw, fh, QImage.Format.Format_Grayscale8)
                mask_img.fill(0)
                painter = QPainter(mask_img)
                painter.setBrush(QBrush(Qt.GlobalColor.white))
                painter.setPen(Qt.PenStyle.NoPen)
                for region in overlapping:
                    poly = QPolygonF([QPointF(p[0] - fx, p[1] - fy) for p in region.points])
                    painter.drawPolygon(poly)
                painter.end()
                mask_img.copy().save(str(mask_path), "PNG")
                saved += 1
            except Exception:
                errors += 1

    if store.regions:
        regions_json_path = annot_dir / f"{stem}_regions.json"
        regions_data = [
            {"id": r.id, "channel": r.channel, "points": [[p[0], p[1]] for p in r.points]}
            for r in store.regions.values()
        ]
        regions_json_path.write_text(json.dumps(regions_data, indent=2))
        saved += 1

    return saved, errors


def load_structured(output_dir: Path, slide_path: Path, store: AnnotationStore) -> int:
    """Load markers, FOVs, and regions from structured annotation directories.

    Returns total number of annotations loaded. Clears the store first.
    """
    stem = slide_path.stem
    marker_annot_dir = output_dir / "Marker Annotations" / "Annot"
    region_annot_dir = output_dir / "Region Annotations" / "Annot"

    if not marker_annot_dir.exists() and not region_annot_dir.exists():
        return 0

    store.clear()
    loaded_fovs: dict[tuple[int, int], str] = {}
    marker_count = 0

    from ..settings import get_settings
    fov_w, fov_h = get_settings().fov_size
    fov_half_w, fov_half_h = fov_w / 2.0, fov_h / 2.0

    # Recover region-only FOVs from PNG filenames in Region Annotations/FOVs/.
    # Filename format: {stem}_{channel}_{x}_{y}.png — coordinates are the last two parts.
    # This mirrors how marker FOVs are recovered from txt file keys.
    region_fovs_dir = output_dir / "Region Annotations" / "FOVs"
    if region_fovs_dir.exists():
        for png_path in sorted(region_fovs_dir.glob(f"{stem}_*.png")):
            parts = png_path.stem[len(stem) + 1 :].split("_")
            if len(parts) < 3:
                continue
            try:
                fov_x, fov_y = int(parts[-2]), int(parts[-1])
            except ValueError:
                continue
            fov_key = (fov_x, fov_y)
            if fov_key not in loaded_fovs:
                fov = store.add_fov(fov_x + fov_half_w, fov_y + fov_half_h)
                loaded_fovs[fov_key] = fov.id

    if marker_annot_dir.exists():
        for txt_path in sorted(marker_annot_dir.glob(f"{stem}_*.txt")):
            channel = txt_path.stem[len(stem) + 1 :]
            for line in txt_path.read_text().splitlines():
                line = line.strip()
                if not line or ":" not in line:
                    continue
                key, boxes_str = line.split(":", 1)
                key = key.strip()
                coord_part = key[len(stem) :]
                coords = coord_part.strip("_").split("_")
                if len(coords) < 2:
                    continue
                try:
                    fov_x, fov_y = int(coords[0]), int(coords[1])
                except ValueError:
                    continue
                fov_key = (fov_x, fov_y)
                if fov_key not in loaded_fovs:
                    fov = store.add_fov(fov_x + fov_half_w, fov_y + fov_half_h)
                    loaded_fovs[fov_key] = fov.id
                for box_str in boxes_str.split():
                    parts = box_str.split(",")
                    if len(parts) != 4:
                        continue
                    bx1, by1, bx2, by2 = map(int, parts)
                    store.add_marker(fov_x + (bx1 + bx2) / 2.0, fov_y + (by1 + by2) / 2.0, channel)
                    marker_count += 1

    region_count = 0
    if region_annot_dir.exists():
        regions_json_path = region_annot_dir / f"{stem}_regions.json"
        if regions_json_path.exists():
            try:
                regions_data = json.loads(regions_json_path.read_text())
                for entry in regions_data:
                    points = [tuple(p) for p in entry["points"]]
                    store.add_region(points, entry["channel"])
                    region_count += 1
            except Exception:
                pass

    store.set_dirty(False)
    return marker_count + region_count
