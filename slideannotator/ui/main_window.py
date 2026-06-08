from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QWidget,
    QVBoxLayout,
)

from ..annotations.models import AnnotationStore
from ..annotations.serializer import load_annotations, save_annotations
from ..compositing.compositor import ChannelSettings
from ..graphics.slide_scene import SlideScene
from ..graphics.slide_view import SlideView
from ..readers import open_slide
from ..tiles.tile_cache import LRUCache
from ..tiles.tile_manager import TileManager
from ..tools.cell_marker_tool import CellMarkerTool
from ..tools.pan_tool import PanTool
from ..tools.region_tool import RegionTool
from ..tools.select_tool import SelectTool
from .annotation_toolbar import AnnotationToolbar
from .channel_panel import ChannelPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SlideAnnotator")
        self.resize(1400, 900)
        self.setStyleSheet("background: #1a1a1a;")

        self._reader = None
        self._store: AnnotationStore | None = None
        self._tile_manager: TileManager | None = None
        self._channel_settings: list[ChannelSettings] = []
        self._active_channel = ""
        self._slide_path: Path | None = None
        self._tools: dict[str, object] = {}
        self._current_tool = None

        self._thread_pool = QThreadPool.globalInstance()
        self._thread_pool.setMaxThreadCount(4)

        self._build_ui()
        self._build_menus()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._toolbar = AnnotationToolbar(self)
        self._toolbar.tool_changed.connect(self._on_tool_changed)
        self._toolbar.annotations_toggled.connect(self._on_annotations_toggled)
        self._toolbar.quit_requested.connect(self.close)
        self.addToolBar(self._toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._channel_panel = ChannelPanel()
        self._channel_panel.setMinimumWidth(200)
        self._channel_panel.setMaximumWidth(280)
        self._channel_panel.channel_visibility_changed.connect(
            self._on_channel_visibility
        )
        self._channel_panel.channel_color_changed.connect(self._on_channel_color)
        self._channel_panel.channel_range_changed.connect(self._on_channel_range)
        self._channel_panel.channel_selected.connect(self._on_active_channel)

        self._view = SlideView()
        splitter.addWidget(self._channel_panel)
        splitter.addWidget(self._view)
        splitter.setSizes([230, 1170])
        layout.addWidget(splitter)

    def _build_menus(self) -> None:
        mb = self.menuBar()
        mb.setStyleSheet(
            "QMenuBar { background: #161616; color: #ccc; }"
            "QMenuBar::item:selected { background: #2a4a7a; }"
            "QMenu { background: #222; color: #ccc; border: 1px solid #444; }"
            "QMenu::item:selected { background: #2a4a7a; }"
        )
        file_menu = mb.addMenu("&File")

        open_action = file_menu.addAction("&Open Image…")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_dialog)

        self._save_action = file_menu.addAction("&Save Annotations")
        self._save_action.setShortcut("Ctrl+S")
        self._save_action.triggered.connect(self._save_annotations)
        self._save_action.setEnabled(False)

        file_menu.addSeparator()
        quit_action = file_menu.addAction("&Quit")
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)

    # ------------------------------------------------------------------
    def _open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Image",
            "",
            "Slide Images (*.tif *.tiff *.svs *.ndpi *.scn *.qptiff *.czi);;All Files (*)",
        )
        if path:
            self.open_image(Path(path))

    def open_image(self, path: Path) -> None:
        if self._store and self._store.is_dirty:
            if not self._prompt_save():
                return

        try:
            if self._reader:
                self._reader.close()

            self._reader = open_slide(path)
            self._slide_path = path

            # Compute quantile-based min/max from smallest pyramid level
            stats_level = self._reader.level_count - 1
            quantiles = self._reader.compute_channel_quantiles(stats_level)

            self._channel_settings = [
                ChannelSettings(
                    visible=True,
                    color=ch.color,
                    min_val=quantiles[i][0],
                    max_val=quantiles[i][1],
                )
                for i, ch in enumerate(self._reader.channels)
            ]

            # Annotation store
            self._store = AnnotationStore()

            # Tile caches + manager
            raw_cache = LRUCache(max_size=500)
            composited_cache = LRUCache(max_size=300)
            self._tile_manager = TileManager(
                self._reader, raw_cache, composited_cache, self._thread_pool
            )

            # Scene
            scene = SlideScene(
                self._tile_manager, self._store, self._channel_settings
            )
            scene.load_slide(self._reader)
            self._view.setScene(scene)
            self._view.fit_to_slide()

            # Channel panel
            self._channel_panel.load_channels(
                self._reader.channels, self._channel_settings
            )

            # Active channel
            if self._reader.channels:
                self._active_channel = self._reader.channels[0].name
                self._toolbar.set_active_channel(self._active_channel)

            # Tools
            self._tools = {
                "pan": PanTool(scene, self._store),
                "cell_marker": CellMarkerTool(scene, self._store),
                "region": RegionTool(scene, self._store, self._view),
                "select": SelectTool(scene, self._store, self._view),
            }
            for tool in self._tools.values():
                tool.active_channel = self._active_channel

            self._on_tool_changed("pan")
            self._toolbar._pan_btn.setChecked(True)

            # Load existing annotations if present
            ann_path = path.with_suffix(path.suffix + ".annotations.json")
            if ann_path.exists():
                load_annotations(ann_path, self._store)

            self._save_action.setEnabled(True)
            self.setWindowTitle(f"SlideAnnotator — {path.name}")

        except Exception as exc:
            QMessageBox.critical(self, "Error Opening Image", str(exc))

    def _save_annotations(self) -> None:
        if self._store is None or self._slide_path is None:
            return
        ann_path = self._slide_path.with_suffix(
            self._slide_path.suffix + ".annotations.json"
        )
        save_annotations(ann_path, self._slide_path, self._store)
        self._store.set_dirty(False)

    # ------------------------------------------------------------------
    def _on_tool_changed(self, name: str) -> None:
        if self._current_tool:
            self._current_tool.deactivate()
        self._current_tool = self._tools.get(name)
        if self._current_tool:
            self._current_tool.activate()
            self._view.set_tool(self._current_tool)

    def _on_annotations_toggled(self, visible: bool) -> None:
        scene = self._view.scene()
        if isinstance(scene, SlideScene):
            scene.set_annotations_visible(visible)

    def _on_channel_visibility(self, index: int, visible: bool) -> None:
        if index < len(self._channel_settings):
            self._channel_settings[index].visible = visible
            self._invalidate_tiles()

    def _on_channel_color(self, index: int, color: tuple) -> None:
        if index < len(self._channel_settings):
            self._channel_settings[index].color = color
            self._invalidate_tiles()

    def _on_channel_range(self, index: int, min_val: float, max_val: float) -> None:
        if index < len(self._channel_settings):
            self._channel_settings[index].min_val = min_val
            self._channel_settings[index].max_val = max_val
            self._invalidate_tiles()

    def _on_active_channel(self, name: str) -> None:
        self._active_channel = name
        for tool in self._tools.values():
            tool.active_channel = name
        self._toolbar.set_active_channel(name)

    def _invalidate_tiles(self) -> None:
        if self._tile_manager:
            self._tile_manager.invalidate_composited_cache()
        scene = self._view.scene()
        if isinstance(scene, SlideScene):
            scene.set_channel_settings(self._channel_settings)
            scene.refresh_thumbnail()
            vr = self._view.mapToScene(
                self._view.viewport().rect()
            ).boundingRect()
            zoom = self._view.current_zoom()
            scene.update_viewport(vr, zoom)

    # ------------------------------------------------------------------
    def _prompt_save(self) -> bool:
        """Ask to save unsaved annotations. Returns True to continue, False to cancel."""
        reply = QMessageBox.question(
            self,
            "Unsaved Annotations",
            "Save annotations before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Save:
            self._save_annotations()
            return True
        if reply == QMessageBox.StandardButton.Discard:
            return True
        return False

    def closeEvent(self, event) -> None:
        if self._store and self._store.is_dirty:
            if not self._prompt_save():
                event.ignore()
                return
        # Cancel queued tile jobs and wait for active ones to finish
        self._thread_pool.clear()
        self._thread_pool.waitForDone(3000)
        if self._reader:
            self._reader.close()
        event.accept()
