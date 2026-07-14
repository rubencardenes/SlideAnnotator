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


def _classify(path: Path, root: Path) -> str:
    """Return "train" or "test" based on the slide's location under ``root``.

    A slide is a test slide if any directory component of its path (relative to
    ``root``) is named ``test``; it is a train slide if a component is named
    ``train``. The shallowest matching component wins. Anything else — including
    slides in no ``train``/``test`` subfolder — defaults to ``train``.
    """
    try:
        rel = path.relative_to(root)
    except ValueError:
        return "train"
    for part in rel.parts[:-1]:  # directory components only, shallow → deep
        low = part.lower()
        if low in ("train", "test"):
            return low
    return "train"


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

        self._train_header = self._make_section_header("Train")
        layout.addWidget(self._train_header)
        self._train_list = self._make_list()
        layout.addWidget(self._train_list)

        self._test_header = self._make_section_header("Test")
        layout.addWidget(self._test_header)
        self._test_list = self._make_list()
        layout.addWidget(self._test_list)

        self._layout = layout

    def _make_section_header(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            "QLabel { background: #202020; color: #9aa4b2;"
            " font-size: 11px; font-weight: bold; letter-spacing: 1px;"
            " padding: 4px 8px; border-top: 1px solid #2a2a2a;"
            " border-bottom: 1px solid #2a2a2a; }"
        )
        return label

    def _make_list(self) -> QListWidget:
        lst = QListWidget()
        lst.setStyleSheet(
            "QListWidget { background: #1e1e1e; border: none; color: #ddd; }"
            "QListWidget::item { padding: 6px 8px; border-bottom: 1px solid #2a2a2a; }"
            "QListWidget::item:selected { background: #2a4a7a; }"
            "QListWidget::item:hover:!selected { background: #252525; }"
        )
        lst.itemDoubleClicked.connect(self._on_double_click)
        return lst

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

        train_paths = [p for p in paths if _classify(p, data_dir) == "train"]
        test_paths = [p for p in paths if _classify(p, data_dir) == "test"]

        self._populate(self._train_list, train_paths, counts)
        self._populate(self._test_list, test_paths, counts)

        # The test section only appears when there are test slides.
        has_test = bool(test_paths)
        self._test_header.setVisible(has_test)
        self._test_list.setVisible(has_test)

        # Share vertical space proportionally to the number of slides in each
        # section so a long train list does not starve a short test list.
        self._layout.setStretchFactor(self._train_list, max(1, len(train_paths)))
        if has_test:
            self._layout.setStretchFactor(self._test_list, max(1, len(test_paths)))

    def _populate(
        self, list_widget: QListWidget, paths: list[Path], counts: dict[str, dict[str, int]]
    ) -> None:
        list_widget.clear()
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
            list_widget.addItem(item)
            list_widget.setItemWidget(item, widget)

    def _on_double_click(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.image_opened.emit(path)

    def update_counts_for(self, slide_name: str, markers: int, regions: int, fovs: int) -> None:
        """Refresh the count display for a single slide after saving."""
        for list_widget in (self._train_list, self._test_list):
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                path = item.data(Qt.ItemDataRole.UserRole)
                if path and path.stem == slide_name:
                    widget = list_widget.itemWidget(item)
                    if isinstance(widget, _ImageItem):
                        widget.set_counts(markers, regions, fovs)
                    return


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
        self._stats_lbl.setText(f"Markers: {markers}   Regions: {regions}   FOVs: {fovs}")
