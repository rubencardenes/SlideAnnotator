from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
)

from ..settings import get_settings


@dataclass
class _MarkerStats:
    slides: set[str] = field(default_factory=set)
    channels: set[str] = field(default_factory=set)
    marker_count: int = 0
    fovs: set[tuple] = field(default_factory=set)  # (slide_stem, x, y)


@dataclass
class _RegionStats:
    slides: set[str] = field(default_factory=set)
    region_count: int = 0
    fovs: set[tuple] = field(default_factory=set)  # (slide_stem, x, y)


def _scan_dir(annot_dir: Path) -> tuple[_MarkerStats, _RegionStats]:
    ms = _MarkerStats()
    rs = _RegionStats()

    # ------------------------------------------------------------------
    # Marker Annotations/Annot/{stem}_{channel}.txt
    # Each line:  {stem}_{fov_x}_{fov_y}: box box ...
    # ------------------------------------------------------------------
    marker_annot = annot_dir / "Marker Annotations" / "Annot"
    if marker_annot.exists():
        for txt in sorted(marker_annot.glob("*.txt")):
            # split off channel (last underscore component)
            parts = txt.stem.rsplit("_", 1)
            if len(parts) != 2 or not parts[0]:
                continue
            slide_stem, channel = parts
            ms.slides.add(slide_stem)
            ms.channels.add(channel)

            for raw_line in txt.read_text().splitlines():
                line = raw_line.strip()
                if not line or ":" not in line:
                    continue
                key, boxes_str = line.split(":", 1)
                key = key.strip()
                # key: {stem}_{fov_x}_{fov_y}  — strip last two int components
                key_parts = key.rsplit("_", 2)
                if len(key_parts) == 3:
                    try:
                        fov_x, fov_y = int(key_parts[1]), int(key_parts[2])
                        ms.fovs.add((key_parts[0], fov_x, fov_y))
                        ms.marker_count += len(boxes_str.split())
                    except ValueError:
                        pass

    # ------------------------------------------------------------------
    # Region Annotations/Annot/{stem}_regions.json
    # Content: [{id, channel, points}, ...]
    # ------------------------------------------------------------------
    region_annot = annot_dir / "Region Annotations" / "Annot"
    if region_annot.exists():
        for jf in sorted(region_annot.glob("*_regions.json")):
            slide_stem = jf.stem[: -len("_regions")]
            if not slide_stem:
                continue
            rs.slides.add(slide_stem)
            try:
                data = json.loads(jf.read_text())
                rs.region_count += len(data)
            except Exception:
                pass

        # Region FOVs come from Region Annotations/FOVs/{stem}_{channel}_{x}_{y}.png
        region_fovs_dir = annot_dir / "Region Annotations" / "FOVs"
        if region_fovs_dir.exists():
            for png in region_fovs_dir.glob("*.png"):
                key_parts = png.stem.rsplit("_", 2)
                if len(key_parts) == 3:
                    try:
                        fov_x, fov_y = int(key_parts[1]), int(key_parts[2])
                        # key_parts[0] is "{stem}_{channel}" — good enough as identity key
                        rs.fovs.add((key_parts[0], fov_x, fov_y))
                    except ValueError:
                        pass

    return ms, rs


# ---------------------------------------------------------------------------
# Dialog helpers
# ---------------------------------------------------------------------------

def _make_section(title: str, rows: list[tuple[str, str, str]]) -> QGroupBox:
    box = QGroupBox(title)
    box.setStyleSheet(
        "QGroupBox {"
        "  color: #ccc; font-size: 13px; font-weight: bold;"
        "  border: 1px solid #3a3a3a; border-radius: 5px;"
        "  margin-top: 10px; padding: 10px 8px 8px 8px;"
        "}"
        "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
    )
    grid = QGridLayout(box)
    grid.setColumnStretch(0, 1)
    grid.setHorizontalSpacing(16)
    grid.setVerticalSpacing(4)

    grid_row = 0
    for label, value, subtext in rows:
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #aaa; font-size: 12px; font-weight: normal;")

        val = QLabel(value)
        val.setStyleSheet("color: #e8e8e8; font-size: 12px; font-weight: bold;")
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        grid.addWidget(lbl, grid_row, 0)
        grid.addWidget(val, grid_row, 1)
        grid_row += 1

        if subtext:
            sub = QLabel(subtext)
            sub.setStyleSheet("color: #666; font-size: 10px; font-weight: normal;")
            sub.setWordWrap(True)
            grid.addWidget(sub, grid_row, 0, 1, 2)
            grid_row += 1

    return box


class SummaryDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Annotation Summary")
        self.setMinimumWidth(380)
        self.setStyleSheet(
            "QDialog { background: #1e1e1e; }"
            "QDialogButtonBox QPushButton {"
            "  background: #2e2e2e; color: #ccc;"
            "  border: 1px solid #444; border-radius: 4px; padding: 4px 16px;"
            "}"
            "QDialogButtonBox QPushButton:hover { background: #3a3a3a; }"
        )

        annot_dir = get_settings().annotations_dir
        ms, rs = _scan_dir(annot_dir)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 10, 14, 14)

        dir_lbl = QLabel(str(annot_dir))
        dir_lbl.setStyleSheet("color: #555; font-size: 10px;")
        dir_lbl.setWordWrap(True)
        layout.addWidget(dir_lbl)

        # -- Marker Annotations --
        channels_str = ""
        if ms.channels:
            names = ", ".join(sorted(ms.channels))
            channels_str = names if len(names) <= 60 else names[:57] + "…"

        marker_rows: list[tuple[str, str, str]] = [
            ("Cell marker annotations", f"{ms.marker_count:,}", ""),
            ("FOVs", f"{len(ms.fovs):,}", ""),
            ("Biomarkers", str(len(ms.channels)), channels_str),
            ("Slides", str(len(ms.slides)), ""),
        ]
        layout.addWidget(_make_section("Marker Annotations", marker_rows))

        # -- Region Annotations --
        region_rows: list[tuple[str, str, str]] = [
            ("Region annotations", f"{rs.region_count:,}", ""),
            ("FOVs", f"{len(rs.fovs):,}", ""),
            ("Slides", str(len(rs.slides)), ""),
        ]
        layout.addWidget(_make_section("Region Annotations", region_rows))

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
