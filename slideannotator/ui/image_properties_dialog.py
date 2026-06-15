from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
)

_EXT_TO_FORMAT = {
    ".tif": "OME-TIFF",
    ".tiff": "OME-TIFF",
    ".qptiff": "OME-TIFF",
    ".ims": "Imaris HDF5",
    ".svs": "Aperio SVS",
    ".ndpi": "Hamamatsu NDPI",
    ".czi": "Zeiss CZI",
    ".scn": "Leica SCN",
}

_BIT_RANGE = {
    8: "8-bit unsigned  (0 – 255)",
    16: "16-bit unsigned  (0 – 65 535)",
    32: "32-bit unsigned  (0 – 4 294 967 295)",
}

_GROUP_STYLE = (
    "QGroupBox {"
    "  color: #ccc; font-size: 13px; font-weight: bold;"
    "  border: 1px solid #3a3a3a; border-radius: 5px;"
    "  margin-top: 10px; padding: 10px 8px 8px 8px;"
    "}"
    "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
)


def _row(grid: QGridLayout, r: int, label: str, value: str) -> None:
    lbl = QLabel(label)
    lbl.setStyleSheet("color: #aaa; font-size: 12px; font-weight: normal;")
    val = QLabel(value)
    val.setStyleSheet("color: #e8e8e8; font-size: 12px; font-weight: bold;")
    val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    grid.addWidget(lbl, r, 0)
    grid.addWidget(val, r, 1)


class ImagePropertiesDialog(QDialog):
    def __init__(self, reader, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Image Properties")
        self.setMinimumWidth(420)
        self.setStyleSheet(
            "QDialog { background: #1e1e1e; }"
            "QDialogButtonBox QPushButton {"
            "  background: #2e2e2e; color: #ccc;"
            "  border: 1px solid #444; border-radius: 4px; padding: 4px 16px;"
            "}"
            "QDialogButtonBox QPushButton:hover { background: #3a3a3a; }"
        )

        meta = getattr(reader, "metadata", {})
        w, h = reader.dimensions
        n_channels = len(reader.channels)
        px_x = meta.get("pixel_size_x", 0.0)
        px_y = meta.get("pixel_size_y", 0.0)
        n_scenes = meta.get("num_scenes", 1)
        bit_depth = meta.get("bit_depth", 16)
        fmt = _EXT_TO_FORMAT.get(reader.path.suffix.lower(), reader.path.suffix.upper())
        bit_str = _BIT_RANGE.get(bit_depth, f"{bit_depth}-bit")

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 10, 14, 14)

        # File path label
        path_lbl = QLabel(str(reader.path))
        path_lbl.setStyleSheet("color: #555; font-size: 10px;")
        path_lbl.setWordWrap(True)
        layout.addWidget(path_lbl)

        # ── Image group ──────────────────────────────────────────────
        img_box = QGroupBox("Image")
        img_box.setStyleSheet(_GROUP_STYLE)
        grid = QGridLayout(img_box)
        grid.setColumnStretch(0, 1)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)

        px_str = (
            f"{px_x:.4f} × {px_y:.4f} µm"
            if px_x or px_y
            else "not available"
        )
        _row(grid, 0, "Format", fmt)
        _row(grid, 1, "Width", f"{w:,} px")
        _row(grid, 2, "Height", f"{h:,} px")
        _row(grid, 3, "Pixel size (X × Y)", px_str)
        _row(grid, 4, "Channels", str(n_channels))
        _row(grid, 5, "Scenes", str(n_scenes))
        _row(grid, 6, "Bit depth", bit_str)
        layout.addWidget(img_box)

        # ── Pyramid group ─────────────────────────────────────────────
        pyr_box = QGroupBox(f"Pyramid  ({reader.level_count} level{'s' if reader.level_count != 1 else ''})")
        pyr_box.setStyleSheet(_GROUP_STYLE)
        pyr_grid = QGridLayout(pyr_box)
        pyr_grid.setHorizontalSpacing(16)
        pyr_grid.setVerticalSpacing(4)

        # Header row
        for col, text in enumerate(("Level", "Width", "Height", "Downsample")):
            hdr = QLabel(text)
            hdr.setStyleSheet("color: #777; font-size: 11px; font-weight: bold;")
            hdr.setAlignment(Qt.AlignmentFlag.AlignRight if col > 0 else Qt.AlignmentFlag.AlignLeft)
            pyr_grid.addWidget(hdr, 0, col)

        for lv in range(reader.level_count):
            lw, lh = reader.level_dimensions[lv]
            ds = reader.level_downsamples[lv]
            ds_str = f"×{ds:.2f}" if ds != int(ds) else f"×{int(ds)}"
            lv_lbl = QLabel(str(lv))
            lv_lbl.setStyleSheet("color: #e8e8e8; font-size: 12px;")
            w_lbl = QLabel(f"{lw:,}")
            w_lbl.setStyleSheet("color: #e8e8e8; font-size: 12px;")
            w_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            h_lbl = QLabel(f"{lh:,}")
            h_lbl.setStyleSheet("color: #e8e8e8; font-size: 12px;")
            h_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            ds_lbl = QLabel(ds_str)
            ds_lbl.setStyleSheet("color: #aaa; font-size: 12px;")
            ds_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            pyr_grid.addWidget(lv_lbl, lv + 1, 0)
            pyr_grid.addWidget(w_lbl, lv + 1, 1)
            pyr_grid.addWidget(h_lbl, lv + 1, 2)
            pyr_grid.addWidget(ds_lbl, lv + 1, 3)

        layout.addWidget(pyr_box)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
