from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..settings import get_settings

_SUFFIXES = {".ome.tif", ".ome.tiff", ".ims", ".czi"}


class ImageListPanel(QWidget):
    image_opened = Signal(Path)

    def __init__(self, get_db: Callable, parent=None) -> None:
        super().__init__(parent)
        self._get_db = get_db
        self._build_ui()

    def _build_ui(self) -> None:
        self.setStyleSheet("background: #1e1e1e;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_widget = QWidget()
        header_widget.setStyleSheet("background: #161616;")
        header = QHBoxLayout(header_widget)
        header.setContentsMargins(8, 6, 8, 6)
        title = QLabel("Images")
        title.setStyleSheet("color: #aaa; font-size: 12px; font-weight: bold;")
        self._refresh_btn = QPushButton("↻")
        self._refresh_btn.setFixedSize(24, 24)
        self._refresh_btn.setToolTip("Refresh image list")
        self._refresh_btn.setStyleSheet(
            "QPushButton { background: #333; color: #aaa; border: none;"
            " border-radius: 3px; font-size: 14px; }"
            "QPushButton:hover { background: #444; }"
        )
        self._refresh_btn.clicked.connect(self.refresh)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._refresh_btn)
        layout.addWidget(header_widget)

        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget { background: #1e1e1e; border: none; color: #ddd; }"
            "QListWidget::item { padding: 6px 8px; border-bottom: 1px solid #2a2a2a; }"
            "QListWidget::item:selected { background: #2a4a7a; }"
            "QListWidget::item:hover:!selected { background: #252525; }"
        )
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)

    def refresh(self) -> None:
        settings = get_settings()
        data_dir = settings.data_dir
        if data_dir is None:
            return
        data_dir = Path(data_dir).expanduser().resolve()
        if not data_dir.exists():
            return

        counts: dict[str, dict[str, int]] = {}
        try:
            db = self._get_db()
            counts = db.get_annotation_counts_by_slide()
        except Exception:
            pass

        def _matches(p: Path) -> bool:
            low = p.name.lower()
            return any(low.endswith(s) for s in _SUFFIXES) and "mask" not in low

        paths = sorted(
            (p for p in data_dir.rglob("*") if p.is_file() and _matches(p)),
            key=lambda p: p.name.lower(),
        )

        self._list.clear()
        for path in paths:
            slide_name = path.stem
            c = counts.get(slide_name, {})
            markers = c.get("cell_marker", 0)
            regions = c.get("region", 0)
            fovs = c.get("fov", 0)

            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(str(path))

            widget = _ImageItem(path.name, markers, regions, fovs)
            widget.adjustSize()
            item.setSizeHint(widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, widget)

    def _on_double_click(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.image_opened.emit(path)

    def update_counts_for(self, slide_name: str, markers: int, regions: int, fovs: int) -> None:
        """Refresh the count display for a single slide after saving."""
        for i in range(self._list.count()):
            item = self._list.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            if path and path.stem == slide_name:
                widget = self._list.itemWidget(item)
                if isinstance(widget, _ImageItem):
                    widget.set_counts(markers, regions, fovs)
                break


class _ImageItem(QWidget):
    def __init__(self, name: str, markers: int, regions: int, fovs: int, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        self._name_lbl = QLabel(name)
        self._name_lbl.setStyleSheet("color: #ddd; font-size: 12px;")
        self._name_lbl.setWordWrap(True)
        self._name_lbl.setMinimumHeight(18)

        self._stats_lbl = QLabel()
        self._stats_lbl.setStyleSheet("color: #888; font-size: 10px;")
        self._stats_lbl.setMinimumHeight(14)
        self.set_counts(markers, regions, fovs)

        layout.addWidget(self._name_lbl)
        layout.addWidget(self._stats_lbl)

    def set_counts(self, markers: int, regions: int, fovs: int) -> None:
        self._stats_lbl.setText(
            f"Markers: {markers}   Regions: {regions}   FOVs: {fovs}"
        )
