from __future__ import annotations

from pathlib import Path

import numpy as np

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QWidget,
    QVBoxLayout,
)

from ..annotations.models import AnnotationStore
from ..inference.stardist import StarDistONNX
from ..inference.stardist_worker import StarDistWorker
from ..settings import get_settings
from ..viewsettings import load_view_settings, save_view_settings
from ..annotations.serializer import export_markers_txt, export_structured, load_structured
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
from .stardist_settings_dialog import StarDistSettingsDialog
from .summary_dialog import SummaryDialog


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
        self._stardist_model: StarDistONNX | None = None
        self._stardist_outline_color = None   # persists across image loads
        self._stardist_outline_width = None

        self._thread_pool = QThreadPool.globalInstance()
        self._thread_pool.setMaxThreadCount(4)

        self._view_settings_timer = QTimer(self)
        self._view_settings_timer.setSingleShot(True)
        self._view_settings_timer.setInterval(1000)
        self._view_settings_timer.timeout.connect(self._save_view_settings)

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
        self._toolbar.marker_box_toggled.connect(self._on_marker_box_toggled)
        self._toolbar.save_requested.connect(self._save_structured)
        self._toolbar.load_requested.connect(self._load_annotations)
        self._toolbar.summary_requested.connect(self._show_summary)
        self._toolbar.run_stardist_requested.connect(self._run_stardist)
        self._toolbar.stardist_toggled.connect(self._on_stardist_toggled)
        self._toolbar.quit_requested.connect(self.close)
        self._toolbar.undo_requested.connect(self._undo)
        self._toolbar.redo_requested.connect(self._redo)
        self._toolbar.stardist_settings_requested.connect(self._show_stardist_settings)
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
        self._view.space_pressed.connect(self._toggle_annotations)
        self._view.b_pressed.connect(self._toggle_marker_boxes)
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
        edit_menu = mb.addMenu("&Edit")
        self._undo_action = edit_menu.addAction("&Undo")
        self._undo_action.setShortcut("Ctrl+Z")
        self._undo_action.triggered.connect(self._undo)
        self._undo_action.setEnabled(False)
        self._redo_action = edit_menu.addAction("&Redo")
        self._redo_action.setShortcut("Ctrl+Shift+Z")
        self._redo_action.triggered.connect(self._redo)
        self._redo_action.setEnabled(False)

        file_menu = mb.addMenu("&File")

        open_action = file_menu.addAction("&Open Image…")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_dialog)

        self._save_action = file_menu.addAction("&Save Annotations")
        self._save_action.setShortcut("Ctrl+S")
        self._save_action.triggered.connect(self._save_structured)
        self._save_action.setEnabled(False)

        self._export_action = file_menu.addAction("&Export Cell Markers (txt)…")
        self._export_action.setShortcut("Ctrl+E")
        self._export_action.triggered.connect(self._export_markers)
        self._export_action.setEnabled(False)

        self._save_fov_action = file_menu.addAction("Save &FOV Images…")
        self._save_fov_action.triggered.connect(self._save_fov_images)
        self._save_fov_action.setEnabled(False)

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
            "Slide Images (*.tif *.tiff *.svs *.ndpi *.scn *.qptiff *.czi *.ims);;All Files (*)",
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
                    visible=i < 10,
                    color=ch.color,
                    min_val=quantiles[i][0],
                    max_val=quantiles[i][1],
                )
                for i, ch in enumerate(self._reader.channels)
            ]
            load_view_settings(path, self._reader.channels, self._channel_settings)

            # Annotation store
            self._store = AnnotationStore()
            self._store.annotation_added.connect(self._update_undo_redo_state)
            self._store.annotation_removed.connect(self._update_undo_redo_state)
            self._store.annotation_moved.connect(self._update_undo_redo_state)

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
            if self._stardist_outline_color is not None:
                scene.set_stardist_style(
                    self._stardist_outline_color, self._stardist_outline_width
                )
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
                "cell_marker": CellMarkerTool(scene, self._store, self._view),
                "region": RegionTool(scene, self._store, self._view),
                "select": SelectTool(scene, self._store, self._view),
            }
            for tool in self._tools.values():
                tool.active_channel = self._active_channel

            self._on_tool_changed("pan")
            self._toolbar._pan_btn.setChecked(True)

            # Reset stardist toggle button state for new image
            self._toolbar._stardist_toggle_btn.setChecked(True)

            # Connect FOV creation from view key shortcut
            self._view.fov_requested.connect(self._on_fov_requested)

            self._save_action.setEnabled(True)
            self._export_action.setEnabled(True)
            self._save_fov_action.setEnabled(True)
            self._toolbar.set_save_load_enabled(True)
            self.setWindowTitle(f"SlideAnnotator — {path.name}")

        except Exception as exc:
            QMessageBox.critical(self, "Error Opening Image", str(exc))

    def _undo(self) -> None:
        if self._store is not None:
            self._store.undo()
            self._update_undo_redo_state()

    def _redo(self) -> None:
        if self._store is not None:
            self._store.redo()
            self._update_undo_redo_state()

    def _update_undo_redo_state(self, *_) -> None:
        can_undo = self._store is not None and self._store.can_undo
        can_redo = self._store is not None and self._store.can_redo
        self._undo_action.setEnabled(can_undo)
        self._redo_action.setEnabled(can_redo)
        self._toolbar.set_undo_redo_enabled(can_undo, can_redo)

    def _export_markers(self) -> None:
        if self._store is None or self._slide_path is None:
            return
        txt_path = self._slide_path.with_suffix(
            self._slide_path.suffix + ".markers.txt"
        )
        export_markers_txt(txt_path, self._slide_path, self._store)
        QMessageBox.information(
            self, "Export Complete", f"Markers exported to:\n{txt_path}"
        )

    def _save_view_settings(self) -> None:
        if self._slide_path is None or self._reader is None:
            return
        save_view_settings(self._slide_path, self._reader.channels, self._channel_settings)

    def _save_structured(self) -> None:
        if self._store is None or self._slide_path is None or self._reader is None:
            return
        output_dir = get_settings().annotations_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        saved, errors = export_structured(
            output_dir, self._slide_path, self._store, self._reader
        )
        self._store.set_dirty(False)
        msg = f"Saved to:\n{output_dir}\n\n{saved} file(s) written."
        if errors:
            msg += f"\n({errors} error(s))"
        QMessageBox.information(self, "Annotations Saved", msg)

    def _load_annotations(self) -> None:
        if self._store is None or self._slide_path is None:
            return
        output_dir = get_settings().annotations_dir
        count = load_structured(output_dir, self._slide_path, self._store)
        scene = self._view.scene()
        if isinstance(scene, SlideScene):
            scene.sync_from_store()
        if count > 0:
            QMessageBox.information(
                self, "Annotations Loaded",
                f"Loaded {count} annotation(s) from:\n{output_dir}"
            )
        else:
            QMessageBox.information(
                self, "No Annotations Found",
                "No saved annotations found for this image."
            )

    def _show_summary(self) -> None:
        dlg = SummaryDialog(parent=self)
        dlg.exec()

    def _on_fov_requested(self, scene_pos) -> None:
        if self._store is None:
            return
        self._store.add_fov(scene_pos.x(), scene_pos.y())

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
            self._view_settings_timer.start()

    def _on_channel_color(self, index: int, color: tuple) -> None:
        if index < len(self._channel_settings):
            self._channel_settings[index].color = color
            self._invalidate_tiles()

    def _on_channel_range(self, index: int, min_val: float, max_val: float) -> None:
        if index < len(self._channel_settings):
            self._channel_settings[index].min_val = min_val
            self._channel_settings[index].max_val = max_val
            self._invalidate_tiles()
            self._view_settings_timer.start()

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

    def _on_marker_box_toggled(self, show: bool) -> None:
        scene = self._view.scene()
        if isinstance(scene, SlideScene):
            scene.set_marker_show_box(show)

    def _toggle_annotations(self) -> None:
        self._toolbar.toggle_annotations_visibility()

    def _toggle_marker_boxes(self) -> None:
        self._toolbar._box_btn.setChecked(not self._toolbar._box_btn.isChecked())

    def _save_fov_images(self) -> None:
        if self._store is None or self._slide_path is None or self._reader is None:
            return

        fovs = list(self._store.fovs.values())
        if not fovs:
            QMessageBox.information(self, "No FOVs", "No FOV annotations to export.")
            return

        images_dir = self._slide_path.parent / "images"
        images_dir.mkdir(exist_ok=True)

        visible: list[tuple] = [
            (i, ch, self._channel_settings[i])
            for i, ch in enumerate(self._reader.channels)
            if i < len(self._channel_settings) and self._channel_settings[i].visible
        ]
        if not visible:
            QMessageBox.information(self, "No Visible Channels", "No channels are visible.")
            return

        def _is_blue(name: str) -> bool:
            n = name.lower()
            return "dapi" in n or "hoechst" in n

        ch_r = ch_g = ch_b = ch_gray = None
        if len(visible) == 1:
            ch_gray = visible[0]
        else:
            blue_list = [t for t in visible if _is_blue(t[1].name)]
            ch_b = blue_list[0] if blue_list else visible[-1]
            rest = [t for t in visible if t is not ch_b]
            ch_r = rest[0] if rest else None
            ch_g = rest[1] if len(rest) > 1 else None

        def _to_u8(arr: np.ndarray, s) -> np.ndarray:
            a = arr.astype(np.float32)
            span = max(float(s.max_val) - float(s.min_val), 1.0)
            return (np.clip((a - float(s.min_val)) / span, 0.0, 1.0) * 255.0).astype(np.uint8)

        stem = self._slide_path.stem
        saved = errors = 0

        for fov in fovs:
            x, y = int(fov.x), int(fov.y)
            w, h = int(fov.w), int(fov.h)
            out_path = images_dir / f"{stem}_{x}_{y}_{w}.png"
            try:
                raw = self._reader.read_region(0, x, y, w, h)
                if ch_gray is not None:
                    idx, _, s = ch_gray
                    data = np.ascontiguousarray(_to_u8(raw[idx], s))
                    qimg = QImage(data.data, w, h, w, QImage.Format.Format_Grayscale8)
                else:
                    rgb = np.zeros((h, w, 3), dtype=np.uint8)
                    if ch_r is not None:
                        rgb[:, :, 0] = _to_u8(raw[ch_r[0]], ch_r[2])
                    if ch_g is not None:
                        rgb[:, :, 1] = _to_u8(raw[ch_g[0]], ch_g[2])
                    if ch_b is not None:
                        rgb[:, :, 2] = _to_u8(raw[ch_b[0]], ch_b[2])
                    data = np.ascontiguousarray(rgb)
                    qimg = QImage(data.data, w, h, w * 3, QImage.Format.Format_RGB888)
                qimg.copy().save(str(out_path), "PNG")
                saved += 1
            except Exception:
                errors += 1

        msg = f"Saved {saved} FOV image(s) to:\n{images_dir}"
        if errors:
            msg += f"\n({errors} error(s))"
        QMessageBox.information(self, "FOV Images Saved", msg)

    # ------------------------------------------------------------------
    def _run_stardist(self) -> None:
        if self._store is None or self._reader is None:
            return

        fovs = list(self._store.fovs.values())
        if not fovs:
            QMessageBox.information(self, "No FOVs", "Add FOV annotations first (F key).")
            return

        channel_idx = None
        for i, ch in enumerate(self._reader.channels):
            n = ch.name.lower()
            if "dapi" in n or "hoechst" in n:
                channel_idx = i
                break
        if channel_idx is None:
            QMessageBox.warning(
                self, "No DAPI/Hoechst Channel",
                "No channel named DAPI or Hoechst found in this image."
            )
            return

        model_path = get_settings().stardist_model
        if model_path is None or not model_path.exists():
            QMessageBox.warning(
                self, "Model Not Found",
                f"StarDist model not found:\n{model_path}\n\nCheck stardist_model in settings.yaml."
            )
            return

        if self._stardist_model is None:
            try:
                self._stardist_model = StarDistONNX(str(model_path))
            except Exception as exc:
                QMessageBox.critical(self, "Model Load Error", str(exc))
                return

        self._toolbar.set_stardist_running(True)
        worker = StarDistWorker(self._stardist_model, fovs, self._reader, channel_idx)
        worker.signals.finished.connect(self._on_stardist_finished)
        worker.signals.error.connect(self._on_stardist_error)
        self._thread_pool.start(worker)

    def _on_stardist_finished(self, polygons: list) -> None:
        self._toolbar.set_stardist_running(False)
        scene = self._view.scene()
        if isinstance(scene, SlideScene):
            scene.set_stardist_polygons(polygons)
        n = len(polygons)
        QMessageBox.information(self, "StarDist Complete", f"Detected {n} cell(s) across all FOVs.")

    def _on_stardist_error(self, msg: str) -> None:
        self._toolbar.set_stardist_running(False)
        QMessageBox.critical(self, "StarDist Error", msg)

    def _on_stardist_toggled(self, visible: bool) -> None:
        scene = self._view.scene()
        if isinstance(scene, SlideScene):
            scene.set_stardist_visible(visible)

    def _show_stardist_settings(self) -> None:
        scene = self._view.scene()
        if not isinstance(scene, SlideScene):
            return
        from PySide6.QtGui import QColor as _QColor
        cur_color = self._stardist_outline_color or _QColor(0, 230, 180)
        cur_width = self._stardist_outline_width or 1
        dlg = StarDistSettingsDialog(cur_color, cur_width, self)
        if dlg.exec():
            self._stardist_outline_color = dlg.selected_color
            self._stardist_outline_width = dlg.selected_width
            scene.set_stardist_style(
                self._stardist_outline_color, self._stardist_outline_width
            )

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
            self._save_structured()
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
