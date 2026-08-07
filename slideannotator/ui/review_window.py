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
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
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
    QVBoxLayout,
    QWidget,
)

from ..annotations.database import AnnotationDB
from ..annotations.models import MARKER_BOX_HALF, AnnotationStore, CellMarker, FOVAnnotation
from ..settings import get_settings
from ..utils.geometry import region_path
from ..utils.groups import TEST, TRAIN, scan_slide_groups

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
    "QCheckBox { color: #ccc; }"
    "QListWidget {"
    "  background: #222; color: #ccc; border: 1px solid #3a3a3a;"
    "  border-radius: 3px;"
    "}"
    "QListWidget::item:selected { background: #2a4a7a; }"
    "QScrollArea { border: none; }"
    "QSlider::groove:horizontal { background: #333; height: 4px; border-radius: 2px; }"
    "QSlider::handle:horizontal {"
    "  background: #4ac26a; width: 12px; height: 12px;"
    "  margin: -4px 0; border-radius: 6px;"
    "}"
    "QSlider::sub-page:horizontal { background: #3a8a52; border-radius: 2px; }"
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


def _collect_fovs(annotations_dir: Path) -> list[FovEntry]:
    """Return all FOV entries found in the unified FOVs directory.

    This mirrors the annotation database 1:1 (see ``sync_fovs_folder`` in
    ``annotations/serializer.py``), so it is used regardless of which
    annotation type is being reviewed.
    """
    subdir = annotations_dir / "FOVs"
    if not subdir.exists():
        return []
    entries: list[FovEntry] = []
    for png in sorted(subdir.glob("*.png")):
        entry = _parse_fov_path(png)
        if entry is not None:
            entries.append(entry)
    return entries


def _load_16bit_png(path: Path) -> np.ndarray | None:
    """Load a 16-bit RGB PNG and return as (H, W, 3) uint16 array.

    Pillow has no native 16-bit-per-channel RGB mode, so ``Image.open`` would
    silently downsample these to 8-bit. Use pyvips instead, which round-trips
    the full precision written by ``_save_fov_rgb16``.
    """
    try:
        import pyvips

        vi = pyvips.Image.new_from_file(str(path))
        mem = vi.write_to_memory()
        arr = np.frombuffer(mem, dtype=np.uint16).reshape((vi.height, vi.width, vi.bands)).copy()
        if arr.shape[2] == 1:
            arr = np.repeat(arr, 3, axis=2)
        elif arr.shape[2] == 4:
            arr = arr[:, :, :3]
        return arr
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


def _compute_auto_range(arr: np.ndarray) -> tuple[int, int, int, int, int, int]:
    """Compute per-channel 1st/99th percentile range from a (H,W,3) uint16 array."""
    result: list[int] = []
    for c in range(3):
        ch = arr[:, :, c]
        if ch.max() == 0:
            result.extend([0, 65535])
        else:
            p1 = int(np.percentile(ch, 1))
            p99 = int(np.percentile(ch, 99))
            if p99 <= p1:
                p99 = min(p1 + 256, 65535)
            result.extend([p1, p99])
    return tuple(result)  # type: ignore[return-value]


def _compute_slider_bounds(arr: np.ndarray) -> tuple[int, int, int]:
    """Compute each channel's slider track bound: 20% above the channel's true max."""
    bounds: list[int] = []
    for c in range(3):
        ch_max = int(arr[:, :, c].max())
        if ch_max == 0:
            bounds.append(65535)
        else:
            bounds.append(min(int(round(ch_max * 1.2)), 65535))
    return tuple(bounds)  # type: ignore[return-value]


def _ndarray_to_qpixmap(arr: np.ndarray) -> QPixmap:
    """Convert an (H, W, 3) uint8 array to a QPixmap."""
    h, w = arr.shape[:2]
    # Ensure C-contiguous
    arr = np.ascontiguousarray(arr)
    qi = QImage(arr.data, w, h, w * 3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qi.copy())


def _find_fov(store: AnnotationStore, x: int, y: int) -> FOVAnnotation | None:
    """Find the FOV in *store* whose (rounded) top-left matches (x, y)."""
    for fov in store.fovs.values():
        if int(round(fov.x)) == x and int(round(fov.y)) == y:
            return fov
    return None


# ---------------------------------------------------------------------------
# Channel range slider
# ---------------------------------------------------------------------------


class _RangeSlider(QWidget):
    """A single horizontal track with two draggable handles (low, high)."""

    rangeChanged = Signal(int, int)

    _HANDLE_R = 7.0
    _GROOVE_H = 4.0

    def __init__(
        self, minimum: int, maximum: int, color: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._min = minimum
        self._max = maximum
        self._low = minimum
        self._high = maximum
        self._color = QColor(color)
        self._active_handle: str | None = None
        self.setMinimumHeight(20)
        self.setFixedHeight(20)

    def low(self) -> int:
        return self._low

    def high(self) -> int:
        return self._high

    def set_range_values(self, low: int, high: int) -> None:
        low = max(self._min, min(int(low), self._max))
        high = max(self._min, min(int(high), self._max))
        if low > high:
            low, high = high, low
        self._low, self._high = low, high
        self.update()

    def set_bounds(self, minimum: int, maximum: int) -> None:
        """Rescale the track itself to [minimum, maximum], clamping handles."""
        if maximum <= minimum:
            maximum = minimum + 1
        self._min, self._max = minimum, maximum
        self._low = max(self._min, min(self._low, self._max))
        self._high = max(self._min, min(self._high, self._max))
        self.update()

    # -- geometry ------------------------------------------------------
    def _span(self) -> float:
        return max(1.0, self.width() - 2 * self._HANDLE_R)

    def _value_to_x(self, value: int) -> float:
        frac = (value - self._min) / max(1, (self._max - self._min))
        return self._HANDLE_R + frac * self._span()

    def _x_to_value(self, x: float) -> int:
        frac = (x - self._HANDLE_R) / self._span()
        frac = min(max(frac, 0.0), 1.0)
        return int(round(self._min + frac * (self._max - self._min)))

    # -- painting --------------------------------------------------------
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        mid_y = self.height() / 2.0

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#333"))
        groove = QRectF(
            self._HANDLE_R,
            mid_y - self._GROOVE_H / 2,
            self.width() - 2 * self._HANDLE_R,
            self._GROOVE_H,
        )
        painter.drawRoundedRect(groove, 2, 2)

        lo_x = self._value_to_x(self._low)
        hi_x = self._value_to_x(self._high)
        selected = QRectF(lo_x, mid_y - self._GROOVE_H / 2, hi_x - lo_x, self._GROOVE_H)
        painter.setBrush(self._color)
        painter.drawRoundedRect(selected, 2, 2)

        handle_pen = QPen(QColor("#111"))
        handle_pen.setWidth(1)
        for x in (lo_x, hi_x):
            painter.setPen(handle_pen)
            painter.setBrush(self._color.lighter(150))
            painter.drawEllipse(QPointF(x, mid_y), self._HANDLE_R, self._HANDLE_R)

        painter.end()

    # -- interaction -----------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        x = event.position().x()
        lo_x = self._value_to_x(self._low)
        hi_x = self._value_to_x(self._high)
        self._active_handle = "low" if abs(x - lo_x) <= abs(x - hi_x) else "high"
        self._drag_to(x)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._active_handle is not None:
            self._drag_to(event.position().x())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._active_handle = None

    def _drag_to(self, x: float) -> None:
        value = self._x_to_value(x)
        if self._active_handle == "low":
            self._low = min(value, self._high)
        else:
            self._high = max(value, self._low)
        self.update()
        self.rangeChanged.emit(self._low, self._high)


class _ChannelSliders(QGroupBox):
    """One two-handle range slider per R/G/B channel, with live min/max labels."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Channel Range", parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 14, 6, 6)

        self._rows: list[tuple[_RangeSlider, QLabel, QLabel]] = []
        for label_text, color in (("R", "#e05a5a"), ("G", "#5ac25a"), ("B", "#5a90e0")):
            row_lbl = QLabel(label_text)
            row_lbl.setFixedWidth(14)
            row_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")

            lo_lbl = QLabel("0")
            lo_lbl.setFixedWidth(48)
            lo_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lo_lbl.setStyleSheet("color: #999; font-size: 11px;")

            hi_lbl = QLabel("65535")
            hi_lbl.setFixedWidth(48)
            hi_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            hi_lbl.setStyleSheet("color: #999; font-size: 11px;")

            slider = _RangeSlider(0, 65535, color)
            slider.rangeChanged.connect(
                lambda lo, hi, lo_l=lo_lbl, hi_l=hi_lbl: (
                    lo_l.setText(str(lo)),
                    hi_l.setText(str(hi)),
                )
            )

            row = QHBoxLayout()
            row.addWidget(row_lbl)
            row.addWidget(lo_lbl)
            row.addWidget(slider, 1)
            row.addWidget(hi_lbl)
            layout.addLayout(row)

            self._rows.append((slider, lo_lbl, hi_lbl))

    def values(self) -> tuple[int, int, int, int, int, int]:
        """Return (r_min, r_max, g_min, g_max, b_min, b_max)."""
        vals = []
        for slider, _lo_lbl, _hi_lbl in self._rows:
            vals.extend([slider.low(), slider.high()])
        return tuple(vals)  # type: ignore[return-value]

    def set_values(
        self, r_min: int, r_max: int, g_min: int, g_max: int, b_min: int, b_max: int
    ) -> None:
        vals = [r_min, r_max, g_min, g_max, b_min, b_max]
        for i, (slider, lo_lbl, hi_lbl) in enumerate(self._rows):
            slider.blockSignals(True)
            slider.set_range_values(vals[i * 2], vals[i * 2 + 1])
            slider.blockSignals(False)
            lo_lbl.setText(str(vals[i * 2]))
            hi_lbl.setText(str(vals[i * 2 + 1]))

    def set_bounds(self, r_max: int, g_max: int, b_max: int) -> None:
        """Rescale each channel's track to [0, Q99] so the full width is usable."""
        maxes = [r_max, g_max, b_max]
        for i, (slider, _lo_lbl, _hi_lbl) in enumerate(self._rows):
            slider.blockSignals(True)
            slider.set_bounds(0, maxes[i])
            slider.blockSignals(False)

    def connect_all(self, slot) -> None:
        for slider, _lo_lbl, _hi_lbl in self._rows:
            slider.rangeChanged.connect(lambda _lo, _hi: slot())


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

        settings = get_settings()
        self._annotations_dir: Path = settings.annotations_dir.expanduser().resolve()
        self._db = AnnotationDB(settings.db_path)
        self._store_cache: dict[str, AnnotationStore] = {}
        # Group is derived from where the slide file actually lives under
        # data_dir; slides not found on disk default to train.
        self._slide_groups: dict[str, str] = (
            scan_slide_groups(settings.data_dir) if settings.data_dir is not None else {}
        )
        self._all_fovs: list[FovEntry] = []
        self._filtered_fovs: list[FovEntry] = []
        self._current_index: int = 0
        self._annot_type: str = "Cell Marker Annotations"
        self._marker_shape: str = "circle"
        self._needs_auto_range: bool = True

        # State for the currently displayed FOV, cached so hover/click
        # editing can redraw the overlay without reloading the image.
        self._current_entry: FovEntry | None = None
        self._current_fov: FOVAnnotation | None = None
        self._current_raw_pix: QPixmap | None = None
        self._current_raw_wh: tuple[int, int] | None = None
        self._hovered_marker_id: str | None = None

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

        dataset_box = QGroupBox("Dataset")
        dataset_layout = QVBoxLayout(dataset_box)
        self._check_train = QCheckBox("Train")
        self._check_train.setChecked(True)
        self._check_test = QCheckBox("Test")
        self._check_test.setChecked(True)
        dataset_layout.addWidget(self._check_train)
        dataset_layout.addWidget(self._check_test)
        self._check_train.toggled.connect(self._apply_filter)
        self._check_test.toggled.connect(self._apply_filter)
        left_layout.addWidget(dataset_box)

        shape_box = QGroupBox("Marker Shape")
        shape_layout = QVBoxLayout(shape_box)
        self._shape_btn = QPushButton("○ Circle")
        self._shape_btn.setCheckable(True)
        self._shape_btn.setChecked(True)
        self._shape_btn.setToolTip("Toggle marker detection shape: circle / square")
        self._shape_btn.clicked.connect(self._on_shape_toggled)
        shape_layout.addWidget(self._shape_btn)
        left_layout.addWidget(shape_box)

        marker_box = QGroupBox("Markers")
        marker_layout = QVBoxLayout(marker_box)
        marker_layout.setContentsMargins(4, 12, 4, 4)
        marker_layout.setSpacing(4)
        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.clicked.connect(lambda: self._set_all_markers(True))
        self._deselect_all_btn = QPushButton("Deselect All")
        self._deselect_all_btn.clicked.connect(lambda: self._set_all_markers(False))
        marker_layout.addWidget(self._select_all_btn)
        marker_layout.addWidget(self._deselect_all_btn)
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
        self._annot_label.setMouseTracking(True)
        # Grab keyboard focus on hover so "d" reaches us instead of being
        # swallowed by whatever widget (e.g. the marker list's type-ahead
        # search) previously held focus.
        self._annot_label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._annot_label.setToolTip(
            "Click: add cell marker    Hover + D: delete cell marker"
        )
        self._annot_label.installEventFilter(self)
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

        opacity_row = QHBoxLayout()
        opacity_lbl = QLabel("Overlay Opacity:")
        opacity_lbl.setStyleSheet("color: #ccc; font-weight: bold;")
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(0, 100)
        self._opacity_slider.setValue(80)
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        self._opacity_val_lbl = QLabel("80%")
        self._opacity_val_lbl.setFixedWidth(36)
        opacity_row.addWidget(opacity_lbl)
        opacity_row.addWidget(self._opacity_slider, 1)
        opacity_row.addWidget(self._opacity_val_lbl)
        bottom_layout.addLayout(opacity_row)

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
        """Reload all FOV entries and repopulate the marker list.

        Only channels that actually have annotations of the currently
        selected type (Cell Marker vs Region) are offered, since an FOV's own
        ``channel`` tag doesn't guarantee it has markers/regions of that kind.
        """
        self._all_fovs = _collect_fovs(self._annotations_dir)

        # Collect unique channels (in stable order) that have annotations of
        # the current type in at least one FOV.
        seen: set[str] = set()
        channels: list[str] = []
        for entry in self._all_fovs:
            if entry.channel in seen:
                continue
            has_annot = (
                bool(self._marker_boxes(entry))
                if self._annot_type == "Cell Marker Annotations"
                else bool(self._overlapping_regions(entry))
            )
            if has_annot:
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

    def _set_all_markers(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self._marker_list.blockSignals(True)
        for i in range(self._marker_list.count()):
            item = self._marker_list.item(i)
            if item:
                item.setCheckState(state)
        self._marker_list.blockSignals(False)
        self._apply_filter()

    def _checked_groups(self) -> set[str]:
        groups: set[str] = set()
        if self._check_train.isChecked():
            groups.add(TRAIN)
        if self._check_test.isChecked():
            groups.add(TEST)
        return groups

    def _apply_filter(self) -> None:
        checked = self._checked_channels()
        groups = self._checked_groups()
        self._filtered_fovs = [
            e
            for e in self._all_fovs
            if e.channel in checked and self._slide_groups.get(e.slide_name, TRAIN) in groups
        ]
        self._current_index = 0
        self._needs_auto_range = True
        self._show_current()

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def _show_current(self) -> None:
        # Moving to a different FOV — persist any pending marker edits first.
        self._flush_dirty_stores()

        self._current_entry = None
        self._current_fov = None
        self._current_raw_pix = None
        self._current_raw_wh = None
        self._hovered_marker_id = None

        if not self._checked_channels():
            self._top_label.setText("No markers selected")
            self._nav_label.setText("")
            blank_style = "background: #111; border: 1px solid #333; " + _PLACEHOLDER_STYLE
            self._raw_label.setText("(no markers selected)")
            self._raw_label.setStyleSheet(blank_style)
            self._annot_label.setText("(no markers selected)")
            self._annot_label.setStyleSheet(blank_style)
            self._prev_btn.setEnabled(False)
            self._next_btn.setEnabled(False)
            return

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

        if self._needs_auto_range:
            r_min, r_max, g_min, g_max, b_min, b_max = _compute_auto_range(arr)
            # Rescale each slider's track to [0, 1.2 * channel max] so the
            # handles use the full width instead of being squeezed near the
            # low end of 65535.
            r_bound, g_bound, b_bound = _compute_slider_bounds(arr)
            self._sliders.set_bounds(r_bound, g_bound, b_bound)
            self._sliders.set_values(r_min, r_max, g_min, g_max, b_min, b_max)
            self._needs_auto_range = False

        r_min, r_max, g_min, g_max, b_min, b_max = self._sliders.values()
        rgb8 = _normalize_channels(arr, r_min, r_max, g_min, g_max, b_min, b_max)

        raw_pix = _ndarray_to_qpixmap(rgb8)

        store = self._get_store(entry.slide_name)
        self._current_entry = entry
        self._current_fov = _find_fov(store, entry.x, entry.y)
        self._current_raw_pix = raw_pix
        self._current_raw_wh = (arr.shape[1], arr.shape[0])

        self._display_pixmap(self._raw_label, raw_pix)
        self._redraw_overlay()

    def _redraw_overlay(self) -> None:
        """Re-render the annotated pixmap from the cached raw image.

        Used after hover/add/delete edits so those stay cheap — no disk
        re-read or channel renormalization needed, just the overlay paint.
        """
        if self._current_entry is None or self._current_raw_pix is None:
            return
        entry = self._current_entry
        annot_pix = self._render_annotated(entry, self._current_raw_pix.copy())
        ann_count = self._count_annotations(entry)
        self._top_label.setText(f"{entry.fov_path.stem}   |   {ann_count} annotation(s)")
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
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self._annot_type == "Cell Marker Annotations":
            self._draw_cell_marker_annot(painter, entry)
        else:
            self._draw_region_annot(painter, entry)

        painter.end()
        return base_pix

    def _overlay_color(self) -> QColor:
        """Green annotation-overlay color, alpha driven by the opacity slider."""
        color = QColor(40, 210, 90)
        color.setAlpha(int(round(self._opacity_slider.value() / 100.0 * 255)))
        return color

    def _get_store(self, slide_name: str) -> AnnotationStore:
        """Return the (cached) annotation store for *slide_name*, loaded from the DB."""
        store = self._store_cache.get(slide_name)
        if store is None:
            store = AnnotationStore()
            self._db.load_for_slide(slide_name, store)
            self._store_cache[slide_name] = store
        return store

    def _markers_in_fov(self, entry: FovEntry) -> list[CellMarker]:
        """Return markers of *entry.channel* located inside the FOV's bounds."""
        store = self._get_store(entry.slide_name)
        fov = _find_fov(store, entry.x, entry.y)
        if fov is None:
            return []
        fx1, fy1 = fov.x, fov.y
        fx2, fy2 = fov.x + fov.w, fov.y + fov.h
        return [
            m
            for m in store.markers.values()
            if m.channel == entry.channel and fx1 <= m.x <= fx2 and fy1 <= m.y <= fy2
        ]

    def _marker_boxes_with_ids(
        self, entry: FovEntry
    ) -> list[tuple[str, int, int, int, int]]:
        """Return (id, bx1, by1, bx2, by2) boxes, relative to the FOV origin, for
        markers of *entry.channel* inside the FOV's bounds."""
        store = self._get_store(entry.slide_name)
        fov = _find_fov(store, entry.x, entry.y)
        if fov is None:
            return []
        fx1, fy1 = fov.x, fov.y
        boxes: list[tuple[str, int, int, int, int]] = []
        for m in self._markers_in_fov(entry):
            bx1 = int(round(m.x - MARKER_BOX_HALF - fx1))
            by1 = int(round(m.y - MARKER_BOX_HALF - fy1))
            bx2 = int(round(m.x + MARKER_BOX_HALF - fx1))
            by2 = int(round(m.y + MARKER_BOX_HALF - fy1))
            boxes.append((m.id, bx1, by1, bx2, by2))
        return boxes

    def _marker_boxes(self, entry: FovEntry) -> list[tuple[int, int, int, int]]:
        """Return (bx1, by1, bx2, by2) boxes, relative to the FOV origin, for
        markers of *entry.channel* inside the FOV's bounds."""
        return [
            (bx1, by1, bx2, by2)
            for _id, bx1, by1, bx2, by2 in self._marker_boxes_with_ids(entry)
        ]

    def _overlapping_regions(self, entry: FovEntry) -> list:
        """Return regions of *entry.channel* whose bbox overlaps the FOV."""
        store = self._get_store(entry.slide_name)
        fov = _find_fov(store, entry.x, entry.y)
        if fov is None:
            return []
        fx, fy = fov.x, fov.y
        fx2, fy2 = fov.x + fov.w, fov.y + fov.h
        overlapping = []
        for region in store.regions.values():
            if region.channel != entry.channel or not region.points:
                continue
            xs = [p[0] for p in region.points]
            ys = [p[1] for p in region.points]
            if max(xs) < fx or min(xs) > fx2 or max(ys) < fy or min(ys) > fy2:
                continue
            overlapping.append(region)
        return overlapping

    def _draw_cell_marker_annot(self, painter: QPainter, entry: FovEntry) -> None:
        """Overlay cell-marker detections on the painter, sourced from the DB.

        Circles are drawn filled; squares are drawn as an outline only, so
        the pixels underneath stay visible. The hovered marker (if any) is
        highlighted so the user knows what "d" would delete.
        """
        marker_boxes = self._marker_boxes_with_ids(entry)
        if not marker_boxes:
            return

        color = self._overlay_color()
        hover_color = QColor("#ffcc33")
        hover_color.setAlpha(color.alpha())

        for marker_id, bx1, by1, bx2, by2 in marker_boxes:
            is_hovered = marker_id == self._hovered_marker_id
            box_color = hover_color if is_hovered else color
            painter.setPen(QPen(box_color, 2 if is_hovered else 1))
            if self._marker_shape == "circle":
                painter.setBrush(box_color)
                cx, cy = (bx1 + bx2) / 2.0, (by1 + by2) / 2.0
                r = MARKER_BOX_HALF / 2.0
                painter.drawEllipse(QPointF(cx, cy), r, r)
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(bx1, by1, bx2 - bx1, by2 - by1)

    def _draw_region_annot(self, painter: QPainter, entry: FovEntry) -> None:
        """Fill overlapping region polygons as a translucent green overlay."""
        store = self._get_store(entry.slide_name)
        fov = _find_fov(store, entry.x, entry.y)
        if fov is None:
            return
        fx, fy = fov.x, fov.y

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._overlay_color())
        for region in self._overlapping_regions(entry):
            shifted_outer = [(p[0] - fx, p[1] - fy) for p in region.points]
            shifted_holes = [[(p[0] - fx, p[1] - fy) for p in ring] for ring in region.holes]
            painter.drawPath(region_path(shifted_outer, shifted_holes))

    def _count_annotations(self, entry: FovEntry) -> int:
        """Return number of annotations for this FOV, sourced from the DB."""
        if self._annot_type == "Cell Marker Annotations":
            return len(self._marker_boxes(entry))
        return len(self._overlapping_regions(entry))

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _go_prev(self) -> None:
        if self._current_index > 0:
            self._current_index -= 1
            self._needs_auto_range = True
            self._show_current()

    def _go_next(self) -> None:
        if self._current_index < len(self._filtered_fovs) - 1:
            self._current_index += 1
            self._needs_auto_range = True
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

    def _on_shape_toggled(self) -> None:
        if self._shape_btn.isChecked():
            self._marker_shape = "circle"
            self._shape_btn.setText("○ Circle")
        else:
            self._marker_shape = "square"
            self._shape_btn.setText("□ Square")
        self._show_current()

    def _on_sliders_changed(self) -> None:
        self._show_current()

    def _on_opacity_changed(self, value: int) -> None:
        self._opacity_val_lbl.setText(f"{value}%")
        self._show_current()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Left:
            self._go_prev()
        elif key == Qt.Key.Key_Right:
            self._go_next()
        elif key == Qt.Key.Key_D:
            self._delete_hovered_marker()
        else:
            super().keyPressEvent(event)

    def done(self, r: int) -> None:
        # Covers every way the dialog can end: Escape (reject), the window's
        # close button, and any explicit accept()/reject() call.
        self._flush_dirty_stores()
        super().done(r)

    # ------------------------------------------------------------------
    # Cell-marker editing (add by click, remove by hover + "d")
    # ------------------------------------------------------------------

    def _flush_dirty_stores(self) -> None:
        """Persist any edited (dirty) annotation stores to the database."""
        for slide_name, store in self._store_cache.items():
            if store.is_dirty:
                self._db.save_all(store, slide_name)
                store.set_dirty(False)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._annot_label:
            if event.type() == QEvent.Type.Enter:
                self._annot_label.setFocus(Qt.FocusReason.MouseFocusReason)
            elif event.type() == QEvent.Type.MouseMove:
                self._on_annot_image_hover(event.position())
            elif (
                event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
            ):
                self._on_annot_image_clicked(event.position())
            elif event.type() == QEvent.Type.Leave:
                self._set_hovered_marker(None)
        return super().eventFilter(obj, event)

    def _label_pos_to_image_xy(self, label: QLabel, pos: QPointF) -> tuple[float, float] | None:
        """Map a click/hover position in *label*'s local coordinates to a
        position in the raw (unscaled) FOV image, or None if outside it."""
        if self._current_raw_wh is None:
            return None
        pix = label.pixmap()
        if pix is None or pix.isNull():
            return None
        raw_w, raw_h = self._current_raw_wh
        pw, ph = pix.width(), pix.height()
        if pw <= 0 or ph <= 0:
            return None
        ox = (label.width() - pw) / 2.0
        oy = (label.height() - ph) / 2.0
        ix = pos.x() - ox
        iy = pos.y() - oy
        if ix < 0 or iy < 0 or ix > pw or iy > ph:
            return None
        return ix * (raw_w / pw), iy * (raw_h / ph)

    def _set_hovered_marker(self, marker_id: str | None) -> None:
        if marker_id == self._hovered_marker_id:
            return
        self._hovered_marker_id = marker_id
        self._redraw_overlay()

    def _on_annot_image_hover(self, pos: QPointF) -> None:
        if self._annot_type != "Cell Marker Annotations" or self._current_entry is None:
            self._set_hovered_marker(None)
            return
        xy = self._label_pos_to_image_xy(self._annot_label, pos)
        if xy is None:
            self._set_hovered_marker(None)
            return
        ix, iy = xy
        hovered_id = None
        for marker_id, bx1, by1, bx2, by2 in self._marker_boxes_with_ids(self._current_entry):
            if bx1 <= ix <= bx2 and by1 <= iy <= by2:
                hovered_id = marker_id
                break
        self._set_hovered_marker(hovered_id)

    def _on_annot_image_clicked(self, pos: QPointF) -> None:
        if (
            self._annot_type != "Cell Marker Annotations"
            or self._current_entry is None
            or self._current_fov is None
        ):
            return
        xy = self._label_pos_to_image_xy(self._annot_label, pos)
        if xy is None:
            return
        ix, iy = xy
        entry = self._current_entry
        fov = self._current_fov
        store = self._get_store(entry.slide_name)
        store.add_marker(fov.x + ix, fov.y + iy, entry.channel)
        self._redraw_overlay()

    def _delete_hovered_marker(self) -> None:
        if self._annot_type != "Cell Marker Annotations":
            return
        if self._hovered_marker_id is None or self._current_entry is None:
            return
        store = self._get_store(self._current_entry.slide_name)
        store.delete(self._hovered_marker_id)
        self._hovered_marker_id = None
        self._redraw_overlay()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Re-scale images after resize
        self._show_current()
