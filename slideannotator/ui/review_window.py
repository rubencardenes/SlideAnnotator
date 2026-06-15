"""Review Annotations window.

Provides a side-by-side FOV viewer with per-channel brightness controls so the
user can inspect exported cell-marker and region annotations without leaving the
application.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..settings import get_settings

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_DARK_STYLE = (
    "QDialog { background: #1a1a1a; color: #ccc; }"
    "QWidget { background: #1a1a1a; color: #ccc; }"
    "QGroupBox {"
    "  color: #ccc; font-size: 12px; font-weight: bold;"
    "  border: 1px solid #3a3a3a; border-radius: 5px;"
    "  margin-top: 10px; padding: 8px 6px 6px 6px;"
    "}"
    "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; }"
    "QPushButton {"
    "  background: #2e2e2e; color: #ccc;"
    "  border: 1px solid #444; border-radius: 4px; padding: 4px 14px;"
    "}"
    "QPushButton:hover { background: #3a3a3a; }"
    "QPushButton:disabled { color: #555; }"
    "QRadioButton { color: #ccc; }"
    "QListWidget {"
    "  background: #222; color: #ccc; border: 1px solid #3a3a3a;"
    "  border-radius: 3px;"
    "}"
    "QListWidget::item:selected { background: #2a4a7a; }"
    "QScrollArea { border: none; }"
    "QSlider::groove:horizontal { background: #333; height: 4px; border-radius: 2px; }"
    "QSlider::handle:horizontal {"
    "  background: #5a7aaa; width: 12px; height: 12px;"
    "  margin: -4px 0; border-radius: 6px;"
    "}"
    "QLabel { color: #ccc; }"
)

_PLACEHOLDER_STYLE = "color: #666; font-size: 14px; font-style: italic;"

# FOV filename pattern: {slide_name}_{channel}_{x}_{y}.png
# Because slide_name and channel may contain underscores we cannot just split
# on "_".  Instead we rely on the last two numeric tokens.
_FOV_RE = re.compile(r"^(.+)_(-?\d+)_(-?\d+)$")


class FovEntry(NamedTuple):
    slide_name: str
    channel: str
    x: int
    y: int
    fov_path: Path


def _parse_fov_path(path: Path) -> FovEntry | None:
    """Parse a FOV PNG filename into its components."""
    stem = path.stem  # e.g. "slide_CD8_1024_2048"
    m = _FOV_RE.match(stem)
    if m is None:
        return None
    # The last two groups are x and y; everything before is "slide_channel"
    prefix = m.group(1)
    x = int(m.group(2))
    y = int(m.group(3))

    # Now split prefix into (slide_name, channel) by trying to match the
    # annotation filename (txt or mask png) which is named {slide}_{channel}.
    # We do a greedy search: the channel is identified by checking which
    # annotation file exists.  If nothing resolves we fall back to splitting
    # on the last underscore.
    parts = prefix.split("_")
    if len(parts) >= 2:
        channel = parts[-1]
        slide_name = "_".join(parts[:-1])
    else:
        channel = prefix
        slide_name = ""
    return FovEntry(slide_name=slide_name, channel=channel, x=x, y=y, fov_path=path)


def _collect_fovs(annot_type: str, annotations_dir: Path) -> list[FovEntry]:
    """Return all FOV entries found in the given annotation type directory."""
    subdir = annotations_dir / annot_type / "FOVs"
    if not subdir.exists():
        return []
    entries: list[FovEntry] = []
    for png in sorted(subdir.glob("*.png")):
        entry = _parse_fov_path(png)
        if entry is not None:
            entries.append(entry)
    return entries


def _load_16bit_png(path: Path) -> np.ndarray | None:
    """Load a 16-bit RGB PNG and return as (H, W, 3) uint16 array."""
    try:
        from PIL import Image

        img = Image.open(str(path))
        arr = np.asarray(img)  # PIL keeps uint16 for 16-bit PNGs
        if arr.ndim == 2:
            arr = np.stack([arr, arr, arr], axis=2)
        elif arr.shape[2] == 4:
            arr = arr[:, :, :3]
        return arr.astype(np.uint16)
    except Exception:
        return None


def _normalize_channels(
    arr: np.ndarray,
    r_min: int,
    r_max: int,
    g_min: int,
    g_max: int,
    b_min: int,
    b_max: int,
) -> np.ndarray:
    """Apply per-channel min/max normalisation and return (H, W, 3) uint8."""
    limits = [(r_min, r_max), (g_min, g_max), (b_min, b_max)]
    channels = []
    for c, (lo, hi) in enumerate(limits):
        ch = arr[:, :, c].astype(np.float32)
        denom = float(hi) - float(lo) + 1e-6
        ch = np.clip((ch - lo) / denom * 255.0, 0, 255).astype(np.uint8)
        channels.append(ch)
    return np.stack(channels, axis=2)


def _ndarray_to_qpixmap(arr: np.ndarray) -> QPixmap:
    """Convert an (H, W, 3) uint8 array to a QPixmap."""
    h, w = arr.shape[:2]
    # Ensure C-contiguous
    arr = np.ascontiguousarray(arr)
    qi = QImage(arr.data, w, h, w * 3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qi.copy())


def _parse_cell_marker_txt(txt_path: Path) -> dict[str, list[tuple[int, int, int, int]]]:
    """Parse a cell-marker annotation txt file.

    Returns a dict mapping FOV key (``{slide}_{x}_{y}``) to a list of
    (bx1, by1, bx2, by2) tuples.
    """
    result: dict[str, list[tuple[int, int, int, int]]] = {}
    if not txt_path.exists():
        return result
    for line in txt_path.read_text().splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, boxes_str = line.split(":", 1)
        key = key.strip()
        boxes: list[tuple[int, int, int, int]] = []
        for tok in boxes_str.split():
            parts = tok.split(",")
            if len(parts) != 4:
                continue
            try:
                bx1, by1, bx2, by2 = map(int, parts)
                boxes.append((bx1, by1, bx2, by2))
            except ValueError:
                continue
        result[key] = boxes
    return result


# ---------------------------------------------------------------------------
# Channel slider group
# ---------------------------------------------------------------------------


class _ChannelSliders(QGroupBox):
    """Three pairs of (min, max) sliders for R/G/B channels."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Channel Range", parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(6, 14, 6, 6)

        self._sliders: list[tuple[QSlider, QSlider]] = []
        for label_text, color in (("R", "#cc4444"), ("G", "#44aa44"), ("B", "#4466cc")):
            row_lbl = QLabel(label_text)
            row_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")

            lo_slider = QSlider(Qt.Orientation.Horizontal)
            lo_slider.setRange(0, 65535)
            lo_slider.setValue(0)
            lo_slider.setToolTip(f"{label_text} min")

            hi_slider = QSlider(Qt.Orientation.Horizontal)
            hi_slider.setRange(0, 65535)
            hi_slider.setValue(65535)
            hi_slider.setToolTip(f"{label_text} max")

            row = QHBoxLayout()
            row.addWidget(row_lbl)
            row.addWidget(lo_slider, 1)
            row.addWidget(hi_slider, 1)
            layout.addLayout(row)

            self._sliders.append((lo_slider, hi_slider))

    def values(self) -> tuple[int, int, int, int, int, int]:
        """Return (r_min, r_max, g_min, g_max, b_min, b_max)."""
        vals = []
        for lo, hi in self._sliders:
            vals.extend([lo.value(), hi.value()])
        return tuple(vals)  # type: ignore[return-value]

    def connect_all(self, slot) -> None:
        for lo, hi in self._sliders:
            lo.valueChanged.connect(slot)
            hi.valueChanged.connect(slot)


# ---------------------------------------------------------------------------
# Review Window
# ---------------------------------------------------------------------------


class ReviewWindow(QDialog):
    """Side-by-side annotation review dialog."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Review Annotations")
        self.resize(1200, 700)
        self.setStyleSheet(_DARK_STYLE)

        self._annotations_dir: Path = get_settings().annotations_dir.expanduser().resolve()
        self._all_fovs: list[FovEntry] = []
        self._filtered_fovs: list[FovEntry] = []
        self._current_index: int = 0
        self._annot_type: str = "Cell Marker Annotations"

        self._build_ui()
        self._refresh_fovs()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ── Left panel ────────────────────────────────────────────────
        left_panel = QWidget()
        left_panel.setFixedWidth(200)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        type_box = QGroupBox("Annotation Type")
        type_layout = QVBoxLayout(type_box)
        self._radio_cell = QRadioButton("Cell Marker")
        self._radio_cell.setChecked(True)
        self._radio_region = QRadioButton("Region")
        type_layout.addWidget(self._radio_cell)
        type_layout.addWidget(self._radio_region)
        self._radio_group = QButtonGroup(self)
        self._radio_group.addButton(self._radio_cell)
        self._radio_group.addButton(self._radio_region)
        self._radio_cell.toggled.connect(self._on_type_changed)
        left_layout.addWidget(type_box)

        marker_box = QGroupBox("Markers")
        marker_layout = QVBoxLayout(marker_box)
        marker_layout.setContentsMargins(4, 12, 4, 4)
        self._marker_list = QListWidget()
        self._marker_list.itemChanged.connect(self._on_marker_filter_changed)
        marker_layout.addWidget(self._marker_list)
        left_layout.addWidget(marker_box, 1)

        root.addWidget(left_panel)

        # ── Centre / image area ───────────────────────────────────────
        centre = QWidget()
        centre_layout = QVBoxLayout(centre)
        centre_layout.setContentsMargins(0, 0, 0, 0)
        centre_layout.setSpacing(6)

        # Top bar — FOV name and count
        self._top_label = QLabel("No FOV selected")
        self._top_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._top_label.setStyleSheet("color: #ccc; font-size: 13px; font-weight: bold;")
        centre_layout.addWidget(self._top_label)

        # Image views
        images_widget = QWidget()
        images_layout = QHBoxLayout(images_widget)
        images_layout.setContentsMargins(0, 0, 0, 0)
        images_layout.setSpacing(8)

        raw_box = QGroupBox("Raw FOV")
        raw_box_layout = QVBoxLayout(raw_box)
        raw_box_layout.setContentsMargins(4, 14, 4, 4)
        self._raw_label = QLabel()
        self._raw_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._raw_label.setMinimumSize(400, 400)
        self._raw_label.setStyleSheet("background: #111; border: 1px solid #333;")
        raw_box_layout.addWidget(self._raw_label)
        images_layout.addWidget(raw_box, 1)

        annot_box = QGroupBox("Annotated")
        annot_box_layout = QVBoxLayout(annot_box)
        annot_box_layout.setContentsMargins(4, 14, 4, 4)
        self._annot_label = QLabel()
        self._annot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._annot_label.setMinimumSize(400, 400)
        self._annot_label.setStyleSheet("background: #111; border: 1px solid #333;")
        annot_box_layout.addWidget(self._annot_label)
        images_layout.addWidget(annot_box, 1)

        centre_layout.addWidget(images_widget, 1)

        # Bottom controls — navigation + sliders
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(4)

        nav_row = QHBoxLayout()
        self._prev_btn = QPushButton("← Prev")
        self._prev_btn.clicked.connect(self._go_prev)
        self._next_btn = QPushButton("Next →")
        self._next_btn.clicked.connect(self._go_next)
        self._nav_label = QLabel("")
        self._nav_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_row.addWidget(self._prev_btn)
        nav_row.addWidget(self._nav_label, 1)
        nav_row.addWidget(self._next_btn)
        bottom_layout.addLayout(nav_row)

        slider_scroll = QScrollArea()
        slider_scroll.setWidgetResizable(True)
        slider_scroll.setMaximumHeight(140)
        slider_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._sliders = _ChannelSliders()
        self._sliders.connect_all(self._on_sliders_changed)
        slider_scroll.setWidget(self._sliders)
        bottom_layout.addWidget(slider_scroll)

        centre_layout.addWidget(bottom)
        root.addWidget(centre, 1)

    # ------------------------------------------------------------------
    # FOV list management
    # ------------------------------------------------------------------

    def _refresh_fovs(self) -> None:
        """Reload all FOV entries and repopulate the marker list."""
        self._all_fovs = _collect_fovs(self._annot_type, self._annotations_dir)

        # Collect unique channels in stable order
        seen: set[str] = set()
        channels: list[str] = []
        for entry in self._all_fovs:
            if entry.channel not in seen:
                seen.add(entry.channel)
                channels.append(entry.channel)

        # Rebuild marker list without firing signals
        self._marker_list.blockSignals(True)
        self._marker_list.clear()
        for ch in sorted(channels):
            item = QListWidgetItem(ch)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self._marker_list.addItem(item)
        self._marker_list.blockSignals(False)

        self._apply_filter()

    def _checked_channels(self) -> set[str]:
        checked: set[str] = set()
        for i in range(self._marker_list.count()):
            item = self._marker_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                checked.add(item.text())
        return checked

    def _apply_filter(self) -> None:
        checked = self._checked_channels()
        self._filtered_fovs = [e for e in self._all_fovs if e.channel in checked]
        self._current_index = 0
        self._show_current()

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def _show_current(self) -> None:
        if not self._filtered_fovs:
            self._top_label.setText("No FOVs found")
            self._nav_label.setText("")
            self._raw_label.setText("No exported annotations found")
            self._raw_label.setStyleSheet(
                "background: #111; border: 1px solid #333; " + _PLACEHOLDER_STYLE
            )
            self._annot_label.setText("")
            self._annot_label.setStyleSheet("background: #111; border: 1px solid #333;")
            self._prev_btn.setEnabled(False)
            self._next_btn.setEnabled(False)
            return

        entry = self._filtered_fovs[self._current_index]
        total = len(self._filtered_fovs)

        self._prev_btn.setEnabled(self._current_index > 0)
        self._next_btn.setEnabled(self._current_index < total - 1)
        self._nav_label.setText(f"{self._current_index + 1} / {total}")

        # Load image
        arr = _load_16bit_png(entry.fov_path)
        if arr is None:
            self._top_label.setText(f"{entry.fov_path.stem}")
            self._raw_label.setText("(image not found)")
            self._raw_label.setStyleSheet(
                "background: #111; border: 1px solid #333; " + _PLACEHOLDER_STYLE
            )
            self._annot_label.setText("")
            return

        r_min, r_max, g_min, g_max, b_min, b_max = self._sliders.values()
        rgb8 = _normalize_channels(arr, r_min, r_max, g_min, g_max, b_min, b_max)

        raw_pix = _ndarray_to_qpixmap(rgb8)

        # Annotated pixmap
        annot_pix = self._render_annotated(entry, raw_pix.copy())

        # Count annotations for top label
        ann_count = self._count_annotations(entry)
        self._top_label.setText(
            f"{entry.fov_path.stem}   |   {ann_count} annotation(s)"
        )

        # Scale and display
        self._display_pixmap(self._raw_label, raw_pix)
        self._display_pixmap(self._annot_label, annot_pix)

    def _display_pixmap(self, label: QLabel, pix: QPixmap) -> None:
        available = label.size()
        if available.width() > 0 and available.height() > 0:
            scaled = pix.scaled(
                available,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            label.setPixmap(scaled)
        else:
            label.setPixmap(pix)

    def _render_annotated(self, entry: FovEntry, base_pix: QPixmap) -> QPixmap:
        """Draw annotations on top of base_pix and return the result."""
        painter = QPainter(base_pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        if self._annot_type == "Cell Marker Annotations":
            self._draw_cell_marker_annot(painter, entry)
        else:
            self._draw_region_annot(painter, entry, base_pix.size())

        painter.end()
        return base_pix

    def _draw_cell_marker_annot(self, painter: QPainter, entry: FovEntry) -> None:
        """Overlay cell-marker bounding boxes on the painter."""
        annot_dir = self._annotations_dir / "Cell Marker Annotations" / "Annot"
        txt_path = annot_dir / f"{entry.slide_name}_{entry.channel}.txt"
        parsed = _parse_cell_marker_txt(txt_path)

        fov_key = f"{entry.slide_name}_{entry.x}_{entry.y}"
        boxes = parsed.get(fov_key, [])
        if not boxes:
            return

        pen = QPen(QColor(255, 220, 0, 200))
        pen.setWidth(2)
        painter.setPen(pen)
        fill = QColor(255, 220, 0, 40)
        painter.setBrush(fill)

        for bx1, by1, bx2, by2 in boxes:
            painter.drawRect(bx1, by1, bx2 - bx1, by2 - by1)

    def _draw_region_annot(self, painter: QPainter, entry: FovEntry, size) -> None:
        """Blend region mask as a semi-transparent green overlay."""
        annot_dir = self._annotations_dir / "Region Annotations" / "Annot"
        mask_path = annot_dir / f"{entry.slide_name}_{entry.channel}_{entry.x}_{entry.y}.png"
        if not mask_path.exists():
            return

        try:
            from PIL import Image

            mask_img = Image.open(str(mask_path)).convert("L")
            mask_arr = np.asarray(mask_img)
        except Exception:
            return

        h, w = mask_arr.shape
        # Build RGBA overlay: green where mask > 0
        overlay = np.zeros((h, w, 4), dtype=np.uint8)
        overlay[mask_arr > 0] = [0, 200, 80, 100]  # semi-transparent green
        overlay_arr = np.ascontiguousarray(overlay)
        qi = QImage(overlay_arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
        overlay_pix = QPixmap.fromImage(qi.copy())
        painter.drawPixmap(0, 0, overlay_pix)

    def _count_annotations(self, entry: FovEntry) -> int:
        """Return number of annotations for this FOV."""
        if self._annot_type == "Cell Marker Annotations":
            annot_dir = self._annotations_dir / "Cell Marker Annotations" / "Annot"
            txt_path = annot_dir / f"{entry.slide_name}_{entry.channel}.txt"
            parsed = _parse_cell_marker_txt(txt_path)
            fov_key = f"{entry.slide_name}_{entry.x}_{entry.y}"
            return len(parsed.get(fov_key, []))
        else:
            annot_dir = self._annotations_dir / "Region Annotations" / "Annot"
            mask_path = annot_dir / f"{entry.slide_name}_{entry.channel}_{entry.x}_{entry.y}.png"
            return 1 if mask_path.exists() else 0

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _go_prev(self) -> None:
        if self._current_index > 0:
            self._current_index -= 1
            self._show_current()

    def _go_next(self) -> None:
        if self._current_index < len(self._filtered_fovs) - 1:
            self._current_index += 1
            self._show_current()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_type_changed(self) -> None:
        if self._radio_cell.isChecked():
            self._annot_type = "Cell Marker Annotations"
        else:
            self._annot_type = "Region Annotations"
        self._refresh_fovs()

    def _on_marker_filter_changed(self, _item) -> None:
        self._apply_filter()

    def _on_sliders_changed(self) -> None:
        self._show_current()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Left:
            self._go_prev()
        elif key == Qt.Key.Key_Right:
            self._go_next()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Re-scale images after resize
        self._show_current()
