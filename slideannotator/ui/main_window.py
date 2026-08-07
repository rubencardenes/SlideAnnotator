from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..annotations.database import AnnotationDB
from ..annotations.eval_database import EvaluationDB
from ..annotations.models import AnnotationStore
from ..annotations.serializer import (
    export_cell_marker_annot,
    export_region_annot,
    needs_cell_marker_fovs,
    needs_region_fovs,
    sync_fovs_folder,
)
from ..compositing.compositor import ChannelSettings
from ..graphics.slide_scene import SlideScene
from ..graphics.slide_view import SlideView
from ..inference.cell_det_worker import CellDetWorker
from ..inference.CellONNXInference import create_cell_detector
from ..inference.eval_worker import EvaluationWorker, FovGT, SlideEvalJob
from ..inference.ONNXInferenceBase import ONNXInferenceBase
from ..inference.stardist import StarDistONNX
from ..inference.stardist_worker import StarDistWorker
from ..readers import open_slide
from ..settings import CellDetModelConfig, get_settings, save_settings
from ..tiles.tile_cache import LRUCache
from ..tiles.tile_manager import TileManager
from ..tools.cell_marker_tool import CellMarkerTool
from ..tools.fov_tool import FovTool
from ..tools.hole_tool import HoleTool
from ..tools.pan_tool import PanTool
from ..tools.region_tool import RegionTool
from ..tools.select_tool import SelectTool
from ..utils.geometry import connected_components, path_to_rings, region_path, split_outer_holes
from ..utils.groups import TEST, TRAIN, scan_slide_files, scan_slide_groups
from ..viewsettings import load_view_settings, save_view_settings
from .agent_panel import AgentPanel
from .annotation_toolbar import AnnotationToolbar
from .channel_panel import ChannelPanel
from .evaluation_dialog import EvaluationResultsDialog, EvaluationSelectionDialog
from .evaluations_table_dialog import EvaluationsTableDialog
from .image_list_panel import ImageListPanel
from .image_properties_dialog import ImagePropertiesDialog
from .marker_selection_dialog import MarkerSelectionDialog
from .review_window import ReviewWindow
from .stardist_settings_dialog import SettingsDialog
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
        self._stardist_outline_color = None  # persists across image loads
        self._stardist_outline_width = None
        self._cell_det_model: ONNXInferenceBase | None = None
        self._cell_det_model_path: Path | None = None
        self._eval_model_name: str | None = None
        self._cell_det_boxes: list[tuple[float, float, float, float]] = []
        self._db: AnnotationDB | None = None
        self._eval_db: EvaluationDB | None = None

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
        self._toolbar.save_requested.connect(self._save_to_db)
        self._toolbar.load_requested.connect(self._load_from_db)
        self._toolbar.summary_requested.connect(self._show_summary)
        self._toolbar.image_properties_requested.connect(self._show_image_properties)
        self._toolbar.run_stardist_requested.connect(self._run_stardist)
        self._toolbar.stardist_toggled.connect(self._on_stardist_toggled)
        self._toolbar.run_cell_det_requested.connect(self._run_cell_det)
        self._toolbar.cell_det_toggled.connect(self._on_cell_det_toggled)
        self._toolbar.cell_det_to_annot_requested.connect(self._cell_det_to_annot)
        self._toolbar.quit_requested.connect(self.close)
        self._toolbar.undo_requested.connect(self._undo)
        self._toolbar.redo_requested.connect(self._redo)
        self._toolbar.stardist_settings_requested.connect(self._show_stardist_settings)
        self._toolbar.region_opacity_changed.connect(self._on_region_opacity_changed)
        self._toolbar.merge_regions_requested.connect(self._merge_regions)
        self.addToolBar(self._toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._image_list_panel = ImageListPanel(get_db=self._get_db)
        self._image_list_panel.setMinimumWidth(180)
        self._image_list_panel.setMaximumWidth(320)
        self._image_list_panel.image_opened.connect(self.open_image)

        self._view = SlideView()
        self._view.space_pressed.connect(self._toggle_annotations)
        self._view.b_pressed.connect(self._toggle_marker_boxes)
        self._view.fov_requested.connect(self._on_fov_requested)
        self._view.marker_requested.connect(self._on_marker_requested)

        self._channel_panel = ChannelPanel()
        self._channel_panel.setMinimumWidth(200)
        self._channel_panel.setMaximumWidth(280)
        self._channel_panel.channel_visibility_changed.connect(self._on_channel_visibility)
        self._channel_panel.channel_color_changed.connect(self._on_channel_color)
        self._channel_panel.channel_range_changed.connect(self._on_channel_range)
        self._channel_panel.channel_selected.connect(self._on_active_channel)

        splitter.addWidget(self._image_list_panel)
        splitter.addWidget(self._view)
        splitter.addWidget(self._channel_panel)
        splitter.setSizes([230, 940, 230])
        layout.addWidget(splitter, 1)

        self._agent_panel = AgentPanel()
        layout.addWidget(self._agent_panel)

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setMaximumHeight(12)
        self._progress_bar.setStyleSheet(
            "QProgressBar { background: #1a1a1a; border: none; }"
            "QProgressBar::chunk { background-color: #2ecc71; }"
        )
        self._progress_bar.setVisible(False)
        self.statusBar().setStyleSheet("background: #161616; border: none;")
        self.statusBar().setContentsMargins(0, 0, 0, 0)
        self.statusBar().addPermanentWidget(self._progress_bar, 1)

        self._image_list_panel.refresh()

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

        self._image_properties_action = file_menu.addAction("Image &Properties…")
        self._image_properties_action.setShortcut("Ctrl+I")
        self._image_properties_action.triggered.connect(self._show_image_properties)
        self._image_properties_action.setEnabled(False)

        self._save_action = file_menu.addAction("&Save Annotations")
        self._save_action.setShortcut("Ctrl+S")
        self._save_action.triggered.connect(self._save_to_db)
        self._save_action.setEnabled(False)

        self._load_action = file_menu.addAction("&Load Annotations")
        self._load_action.setShortcut("Ctrl+L")
        self._load_action.triggered.connect(self._load_from_db)
        self._load_action.setEnabled(False)

        self._export_cell_marker_action = file_menu.addAction("Export Cell Marker &Annot…")
        self._export_cell_marker_action.setShortcut("Ctrl+E")
        self._export_cell_marker_action.triggered.connect(self._export_cell_marker_annot)

        self._export_region_action = file_menu.addAction("Export &Region Annot…")
        self._export_region_action.setShortcut("Ctrl+Shift+E")
        self._export_region_action.triggered.connect(self._export_region_annot)

        self._review_action = file_menu.addAction("Re&view Annotations…")
        self._review_action.setShortcut("Ctrl+R")
        self._review_action.triggered.connect(self._show_review_window)

        self._evaluate_action = file_menu.addAction("E&valuate…")
        self._evaluate_action.triggered.connect(self._show_evaluate)

        self._show_evaluations_action = file_menu.addAction("Sho&w Evaluations…")
        self._show_evaluations_action.triggered.connect(self._show_evaluations)

        file_menu.addSeparator()
        self._refresh_paths_action = file_menu.addAction("Refresh File &Locations…")
        self._refresh_paths_action.setToolTip(
            "Update the slide file paths stored in the database to match their "
            "current location under data_dir."
        )
        self._refresh_paths_action.triggered.connect(self._refresh_file_locations)

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
            self._store.annotation_added.connect(self._refresh_fov_counts)
            self._store.annotation_removed.connect(self._refresh_fov_counts)

            # Tile caches + manager
            raw_cache = LRUCache(max_size=500)
            composited_cache = LRUCache(max_size=300)
            self._tile_manager = TileManager(
                self._reader, raw_cache, composited_cache, self._thread_pool
            )

            # Scene
            scene = SlideScene(self._tile_manager, self._store, self._channel_settings)
            scene.load_slide(self._reader)
            if self._stardist_outline_color is not None:
                scene.set_stardist_style(self._stardist_outline_color, self._stardist_outline_width)
            self._view.setScene(scene)
            self._view.fit_to_slide()

            # Channel panel
            self._channel_panel.load_channels(self._reader.channels, self._channel_settings)

            # Active channel
            if self._reader.channels:
                self._active_channel = self._reader.channels[0].name
                self._toolbar.set_active_channel(self._active_channel)

            # Tools
            self._tools = {
                "pan": PanTool(scene, self._store),
                "cell_marker": CellMarkerTool(scene, self._store, self._view),
                "fov": FovTool(scene, self._store, self._view),
                "region": RegionTool(scene, self._store, self._view),
                "region_hole": HoleTool(scene, self._store, self._view),
                "select": SelectTool(scene, self._store, self._view),
            }
            for tool in self._tools.values():
                tool.active_channel = self._active_channel

            self._on_tool_changed("pan")
            self._toolbar._pan_btn.setChecked(True)

            # Auto-load saved annotations for this slide (silent — no dialog)
            self._get_db().load_for_slide(self._slide_path.stem, self._store)
            scene.set_active_channel(self._active_channel)
            scene.sync_from_store()

            # Reset inference toggle/convert button states for new image
            self._toolbar._stardist_toggle_btn.setChecked(True)
            self._toolbar._cell_det_toggle_btn.setChecked(True)
            self._cell_det_boxes = []
            self._toolbar.set_cell_det_convert_enabled(False)

            self._save_action.setEnabled(True)
            self._load_action.setEnabled(True)
            self._image_properties_action.setEnabled(True)
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

    def _refresh_fov_counts(self, *_) -> None:
        if self._store is None:
            return
        counts: dict[str, int] = {}
        for fov in self._store.fovs.values():
            counts[fov.channel] = counts.get(fov.channel, 0) + 1
        self._channel_panel.update_fov_counts(counts)

    def _export_cell_marker_annot(self) -> None:
        db = self._get_db()
        channels = db.get_distinct_channels("cell_marker")
        dlg = MarkerSelectionDialog(
            channels, title="Select Markers to Export", parent=self, show_format_choice=True
        )
        if dlg.exec() != MarkerSelectionDialog.DialogCode.Accepted:
            return
        selected = set(dlg.selected_channels())
        export_format = dlg.export_format()

        output_dir = get_settings().annotations_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        current_stem = self._slide_path.stem if self._slide_path else None
        saved = errors = 0
        for slide_name, slide_path in db.get_slide_paths().items():
            temp_store = AnnotationStore()
            db.load_for_slide(slide_name, temp_store)
            reader = None
            opened = False
            if slide_name == current_stem:
                reader = self._reader
            elif needs_cell_marker_fovs(output_dir, slide_name, temp_store):
                if slide_path and slide_path.exists():
                    try:
                        reader = open_slide(slide_path)
                        opened = True
                    except Exception:
                        pass
            try:
                s, e = export_cell_marker_annot(
                    output_dir,
                    slide_name,
                    temp_store,
                    reader,
                    selected_channels=selected,
                    export_format=export_format,
                )
            finally:
                if opened and reader is not None:
                    reader.close()
            saved += s
            errors += e
        msg = (
            f"Exported ({export_format.upper()}) to:\n"
            f"{output_dir / 'Cell Marker Annotations'}\n\n{saved} file(s) written."
        )
        if errors:
            msg += f"\n({errors} error(s))"
        QMessageBox.information(self, "Cell Marker Annotations Exported", msg)

    def _save_view_settings(self) -> None:
        if self._slide_path is None or self._reader is None:
            return
        save_view_settings(self._slide_path, self._reader.channels, self._channel_settings)

    def _get_db(self) -> AnnotationDB:
        if self._db is None:
            self._db = AnnotationDB(get_settings().db_path)
        return self._db

    def _get_eval_db(self) -> EvaluationDB:
        if self._eval_db is None:
            self._eval_db = EvaluationDB(get_settings().resolved_eval_db_path())
        return self._eval_db

    def _save_to_db(self) -> None:
        if self._store is None or self._slide_path is None:
            return
        db = self._get_db()
        count = db.save_all(self._store, self._slide_path.stem)
        db.record_slide_path(self._slide_path.stem, self._slide_path)
        self._store.set_dirty(False)
        slide_name = self._slide_path.stem
        self._image_list_panel.update_counts_for(
            slide_name,
            len(self._store.markers),
            len(self._store.regions),
            len(self._store.fovs),
        )
        written, deleted, fov_errors = sync_fovs_folder(
            get_settings().annotations_dir, slide_name, self._store, self._reader
        )
        msg = f"Saved {count} annotation(s) to database."
        if written or deleted:
            msg += f"\nFOVs folder: {written} image(s) added, {deleted} removed."
        if fov_errors:
            msg += f"\n({fov_errors} FOV image error(s))"
        QMessageBox.information(self, "Annotations Saved", msg)

    def _load_from_db(self) -> None:
        if self._store is None or self._slide_path is None:
            return
        count = self._get_db().load_for_slide(self._slide_path.stem, self._store)
        scene = self._view.scene()
        if isinstance(scene, SlideScene):
            scene.sync_from_store()
        if count > 0:
            QMessageBox.information(
                self, "Annotations Loaded", f"Loaded {count} annotation(s) from database."
            )
        else:
            QMessageBox.information(
                self, "No Annotations Found", "No saved annotations found for this image."
            )

    def _export_region_annot(self) -> None:
        db = self._get_db()
        channels = db.get_distinct_channels("region")
        dlg = MarkerSelectionDialog(channels, title="Select Markers to Export", parent=self)
        if dlg.exec() != MarkerSelectionDialog.DialogCode.Accepted:
            return
        selected = set(dlg.selected_channels())

        output_dir = get_settings().annotations_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        current_stem = self._slide_path.stem if self._slide_path else None
        saved = errors = 0
        for slide_name, slide_path in db.get_slide_paths().items():
            temp_store = AnnotationStore()
            db.load_for_slide(slide_name, temp_store)
            reader = None
            opened = False
            if slide_name == current_stem:
                reader = self._reader
            elif needs_region_fovs(output_dir, slide_name, temp_store):
                if slide_path and slide_path.exists():
                    try:
                        reader = open_slide(slide_path)
                        opened = True
                    except Exception:
                        pass
            try:
                s, e = export_region_annot(
                    output_dir,
                    slide_name,
                    temp_store,
                    reader,
                    selected_channels=selected,
                )
            finally:
                if opened and reader is not None:
                    reader.close()
            saved += s
            errors += e
        msg = f"Exported to:\n{output_dir / 'Region Annotations'}\n\n{saved} file(s) written."
        if errors:
            msg += f"\n({errors} error(s))"
        QMessageBox.information(self, "Region Annotations Exported", msg)

    def _show_image_properties(self) -> None:
        if self._reader is None:
            return
        dlg = ImagePropertiesDialog(self._reader, parent=self)
        dlg.exec()

    def _show_summary(self) -> None:
        dlg = SummaryDialog(parent=self)
        dlg.exec()

    def _show_review_window(self) -> None:
        dlg = ReviewWindow(parent=self)
        dlg.exec()

    # ------------------------------------------------------------------
    def _refresh_file_locations(self) -> None:
        """Rewrite the DB's recorded slide paths to match files on disk."""
        settings = get_settings()
        if settings.data_dir is None:
            QMessageBox.warning(
                self,
                "No Data Directory",
                "No data_dir is configured in settings.yaml.",
            )
            return

        files = scan_slide_files(settings.data_dir)
        db = self._get_db()
        current = db.get_slide_paths()

        updated = 0
        unchanged = 0
        not_found: list[str] = []
        for slide_name, old_path in current.items():
            new_path = files.get(slide_name)
            if new_path is None:
                not_found.append(slide_name)
                continue
            if old_path is None or Path(old_path) != new_path:
                db.record_slide_path(slide_name, new_path)
                updated += 1
            else:
                unchanged += 1

        lines = [
            f"Updated: {updated}",
            f"Already up to date: {unchanged}",
            f"Not found on disk: {len(not_found)}",
        ]
        if not_found:
            lines.append("")
            lines.append("Not found:")
            lines.extend(f"  • {name}" for name in not_found)
        QMessageBox.information(self, "Refresh File Locations", "\n".join(lines))

    # ------------------------------------------------------------------
    # Model evaluation
    def _load_cell_det_model(self, model_cfg: CellDetModelConfig) -> ONNXInferenceBase | None:
        """Load (or reuse the cached) cell detector for ``model_cfg``."""
        if not model_cfg.path.exists():
            QMessageBox.warning(
                self,
                "Model Not Found",
                f"Cell detection model not found:\n{model_cfg.path}\n\n"
                "Check cell_det_models in settings.yaml.",
            )
            return None
        if self._cell_det_model is None or self._cell_det_model_path != model_cfg.path:
            try:
                self._cell_det_model = create_cell_detector(
                    str(model_cfg.path), device="cpu", normalize_scheme=model_cfg.norm
                )
                self._cell_det_model_path = model_cfg.path
            except Exception as exc:
                QMessageBox.critical(self, "Model Load Error", str(exc))
                return None
        return self._cell_det_model

    def _show_evaluate(self) -> None:
        db = self._get_db()
        markers = db.get_distinct_channels("cell_marker")
        slide_paths = db.get_slide_paths()
        images = list(slide_paths.keys())
        if not markers or not images:
            QMessageBox.information(
                self,
                "Nothing to Evaluate",
                "No cell-marker annotations found in the database.",
            )
            return

        settings = get_settings()
        if not settings.cell_det_models:
            QMessageBox.warning(
                self,
                "No Model Registered",
                "No cell detection models registered. Add one under cell_det_models "
                "in settings.yaml or via the Settings dialog.",
            )
            return

        # Tag each slide (and thereby each marker) with its train/test group so
        # the dialog can filter by group. Group is derived from where the slide
        # file actually lives under data_dir (the paths recorded in the DB can be
        # stale); slides not found on disk default to train.
        group_by_stem = (
            scan_slide_groups(settings.data_dir) if settings.data_dir is not None else {}
        )
        image_groups = {name: {group_by_stem.get(name, TRAIN)} for name in slide_paths}
        marker_groups: dict[str, set[str]] = {}
        for slide_name, channels in db.get_channels_by_slide("cell_marker").items():
            groups = image_groups.get(slide_name, {TRAIN})
            for channel in channels:
                marker_groups.setdefault(channel, set()).update(groups)

        dlg = EvaluationSelectionDialog(
            markers,
            images,
            seg_available=settings.seg_model is not None,
            cell_det_models=settings.cell_det_models,
            image_groups=image_groups,
            marker_groups=marker_groups,
            default_group=TEST,
            parent=self,
        )
        if dlg.exec() != EvaluationSelectionDialog.DialogCode.Accepted:
            return

        selected_markers = set(dlg.selected_markers())
        selected_images = dlg.selected_images()
        iou_threshold = dlg.iou_threshold()
        task = dlg.task_type()
        model_cfg = dlg.selected_model()

        if not selected_markers or not selected_images:
            QMessageBox.warning(
                self, "Nothing Selected", "Select at least one marker and one image."
            )
            return

        if task == "segmentation":
            # Coded but inactive: the segmentation path needs a configured model.
            QMessageBox.information(
                self,
                "Segmentation Not Available",
                "Semantic segmentation evaluation requires a segmentation model "
                "(set seg_model in settings.yaml).",
            )
            return

        jobs = self._build_eval_jobs(selected_images, slide_paths, selected_markers)
        total_fovs = sum(len(job.fovs) for job in jobs)
        if total_fovs == 0:
            QMessageBox.warning(
                self,
                "No Annotations Available",
                "No annotations with this image / marker selection are available.",
            )
            return

        cell_det_model = self._load_cell_det_model(model_cfg)
        if cell_det_model is None:
            return

        self._eval_model_name = model_cfg.name
        self._evaluate_action.setEnabled(False)
        self._progress_bar.setValue(0)
        self._progress_bar.setMaximum(total_fovs)
        self._progress_bar.setVisible(True)
        worker = EvaluationWorker(cell_det_model, jobs, iou_threshold)
        worker.signals.progress.connect(self._on_eval_progress)
        worker.signals.finished.connect(self._on_eval_finished)
        worker.signals.error.connect(self._on_eval_error)
        self._thread_pool.start(worker)

    def _build_eval_jobs(
        self, slide_names: list[str], slide_paths: dict, selected_markers: set[str]
    ) -> list[SlideEvalJob]:
        """Load ground-truth FOV boxes from the database for each slide."""
        jobs: list[SlideEvalJob] = []
        for slide_name in slide_names:
            path = slide_paths.get(slide_name)
            if not path or not path.exists():
                continue
            temp_store = AnnotationStore()
            self._get_db().load_for_slide(slide_name, temp_store)
            fov_gts: list[FovGT] = []
            for fov in temp_store.fovs.values():
                boxes_by_marker: dict[str, list] = {}
                for m in temp_store.markers.values():
                    if m.channel not in selected_markers:
                        continue
                    if fov.x <= m.x <= fov.x + fov.w and fov.y <= m.y <= fov.y + fov.h:
                        box = (m.x - m.w / 2, m.y - m.h / 2, m.x + m.w / 2, m.y + m.h / 2)
                        boxes_by_marker.setdefault(m.channel, []).append(box)
                if boxes_by_marker:
                    fov_gts.append(
                        FovGT(
                            int(fov.x),
                            int(fov.y),
                            int(fov.w),
                            int(fov.h),
                            boxes_by_marker,
                        )
                    )
            if fov_gts:
                jobs.append(SlideEvalJob(slide_name, path, fov_gts))
        return jobs

    def _on_eval_progress(self, done: int, total: int) -> None:
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(done)

    def _on_eval_finished(self, result) -> None:
        self._progress_bar.setVisible(False)
        self._evaluate_action.setEnabled(True)
        model_name = self._eval_model_name or "cell_det_model"
        try:
            self._get_eval_db().save_evaluation(result, model_name)
        except Exception as exc:
            QMessageBox.warning(self, "Could Not Save Evaluation", str(exc))
        dlg = EvaluationResultsDialog(result, parent=self)
        dlg.exec()

    def _show_evaluations(self) -> None:
        db = self._get_eval_db()
        records = db.get_evaluations()
        dlg = EvaluationsTableDialog(records, db=db, parent=self)
        dlg.exec()

    def _on_eval_error(self, msg: str) -> None:
        self._progress_bar.setVisible(False)
        self._evaluate_action.setEnabled(True)
        QMessageBox.critical(self, "Evaluation Error", msg)

    def _on_fov_requested(self, scene_pos) -> None:
        if self._store is None:
            return
        self._store.add_fov(scene_pos.x(), scene_pos.y(), channel=self._active_channel)

    def _on_marker_requested(self, scene_pos) -> None:
        if self._store is None:
            return
        self._store.add_marker(scene_pos.x(), scene_pos.y(), self._active_channel)

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
        scene = self._view.scene()
        if isinstance(scene, SlideScene):
            scene.set_active_channel(name)

    def _invalidate_tiles(self) -> None:
        if self._tile_manager:
            self._tile_manager.invalidate_composited_cache()
        scene = self._view.scene()
        if isinstance(scene, SlideScene):
            scene.set_channel_settings(self._channel_settings)
            scene.refresh_thumbnail()
            vr = self._view.mapToScene(self._view.viewport().rect()).boundingRect()
            zoom = self._view.current_zoom()
            scene.update_viewport(vr, zoom)

    def _merge_regions(self) -> None:
        if self._store is None:
            return
        regions = [r for r in self._store.regions.values() if r.channel == self._active_channel]
        if len(regions) < 2:
            QMessageBox.information(
                self,
                "Nothing to Merge",
                "Need at least two region annotations on the active channel to merge.",
            )
            return
        paths = [region_path(r.points, r.holes) for r in regions]
        groups = connected_components(paths)
        merges: list[dict] = []
        for group in groups:
            if len(group) < 2:
                continue
            merged = paths[group[0]]
            for idx in group[1:]:
                merged = merged.united(paths[idx])
            outer, holes = split_outer_holes(path_to_rings(merged))
            if not outer:
                continue
            first = regions[group[0]]
            merges.append(
                {
                    "remove_ids": [regions[i].id for i in group],
                    "points": outer,
                    "holes": holes,
                    "channel": first.channel,
                    "color": first.color,
                }
            )
        if not merges:
            QMessageBox.information(
                self,
                "Nothing to Merge",
                "No touching or overlapping regions found on the active channel.",
            )
            return
        self._store.merge_regions(merges)
        self._update_undo_redo_state()

    def _on_region_opacity_changed(self, opacity: float) -> None:
        scene = self._view.scene()
        if isinstance(scene, SlideScene):
            scene.set_region_fill_opacity(opacity)

    def _on_marker_box_toggled(self, show: bool) -> None:
        scene = self._view.scene()
        if isinstance(scene, SlideScene):
            scene.set_marker_show_box(show)

    def _toggle_annotations(self) -> None:
        self._toolbar.toggle_annotations_visibility()

    def _toggle_marker_boxes(self) -> None:
        self._toolbar._box_btn.setChecked(not self._toolbar._box_btn.isChecked())

    # ------------------------------------------------------------------
    def _run_stardist(self) -> None:
        if self._store is None or self._reader is None:
            return

        selected_fov_ids = {aid for aid in self._store.selected if aid in self._store.fovs}
        if selected_fov_ids:
            fovs = [self._store.fovs[aid] for aid in selected_fov_ids]
        else:
            fovs = [f for f in self._store.fovs.values() if f.channel == self._active_channel]
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
                self,
                "No DAPI/Hoechst Channel",
                "No channel named DAPI or Hoechst found in this image.",
            )
            return

        model_path = get_settings().stardist_model
        if model_path is None or not model_path.exists():
            QMessageBox.warning(
                self,
                "Model Not Found",
                f"StarDist model not found:\n{model_path}\n\nCheck stardist_model in settings.yaml.",
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
        QMessageBox.information(self, "StarDist Complete", f"Detected {n} nucleus/nuclei.")

    def _on_stardist_error(self, msg: str) -> None:
        self._toolbar.set_stardist_running(False)
        QMessageBox.critical(self, "StarDist Error", msg)

    def _on_stardist_toggled(self, visible: bool) -> None:
        scene = self._view.scene()
        if isinstance(scene, SlideScene):
            scene.set_stardist_visible(visible)

    def _show_stardist_settings(self) -> None:
        from PySide6.QtGui import QColor as _QColor

        dlg = SettingsDialog(get_settings(), self)
        if dlg.exec():
            new_s = dlg.get_settings()
            save_settings(new_s)
            self._stardist_outline_color = _QColor(*new_s.outline_color)
            self._stardist_outline_width = new_s.outline_thickness
            scene = self._view.scene()
            if isinstance(scene, SlideScene):
                scene.set_stardist_style(self._stardist_outline_color, self._stardist_outline_width)
                scene.set_region_fill_opacity(new_s.region_opacity / 100.0)

    # ------------------------------------------------------------------
    def _run_cell_det(self) -> None:
        if self._store is None or self._reader is None:
            return

        selected_fov_ids = {aid for aid in self._store.selected if aid in self._store.fovs}
        if selected_fov_ids:
            fovs = [self._store.fovs[aid] for aid in selected_fov_ids]
        else:
            fovs = [f for f in self._store.fovs.values() if f.channel == self._active_channel]
        if not fovs:
            QMessageBox.information(self, "No FOVs", "Add FOV annotations first (F key).")
            return

        settings = get_settings()
        model_cfg = settings.default_cell_det_model()
        if model_cfg is None:
            QMessageBox.warning(
                self,
                "No Model Registered",
                "No cell detection models registered. Add one under cell_det_models "
                "in settings.yaml or via the Settings dialog.",
            )
            return

        if self._load_cell_det_model(model_cfg) is None:
            return

        # Locate DAPI/Hoechst channel and the active marker channel.
        dapi_idx = None
        for i, ch in enumerate(self._reader.channels):
            n = ch.name.lower()
            if "dapi" in n or "hoechst" in n:
                dapi_idx = i
                break
        if dapi_idx is None:
            QMessageBox.warning(
                self,
                "No DAPI/Hoechst Channel",
                "No DAPI or Hoechst channel found. Cannot run cell detection.",
            )
            return

        marker_idx = None
        for i, ch in enumerate(self._reader.channels):
            if ch.name == self._active_channel:
                marker_idx = i
                break
        if marker_idx is None:
            QMessageBox.warning(
                self,
                "No Active Channel",
                "No active channel selected. Click a channel in the channel panel first.",
            )
            return

        channel_r = marker_idx  # tile[0] = marker  (red channel)
        channel_g = None  # tile[1] = zeros   (green channel empty)
        channel_b = dapi_idx  # tile[2] = DAPI    (blue channel)

        self._toolbar.set_cell_det_running(True)
        self._progress_bar.setValue(0)
        self._progress_bar.setMaximum(len(fovs))
        self._progress_bar.setVisible(True)
        worker = CellDetWorker(
            self._cell_det_model, fovs, self._reader, channel_r, channel_g, channel_b
        )
        worker.signals.progress.connect(self._on_cell_det_progress)
        worker.signals.finished.connect(self._on_cell_det_finished)
        worker.signals.error.connect(self._on_cell_det_error)
        self._thread_pool.start(worker)

    def _on_cell_det_progress(self, done: int, total: int) -> None:
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(done)

    def _on_cell_det_finished(self, boxes: list) -> None:
        self._toolbar.set_cell_det_running(False)
        self._progress_bar.setVisible(False)
        self._cell_det_boxes = boxes
        centers = [((x0 + x1) / 2.0, (y0 + y1) / 2.0) for x0, y0, x1, y1 in boxes]
        scene = self._view.scene()
        if isinstance(scene, SlideScene):
            scene.set_cell_det_points(centers)
        self._toolbar.set_cell_det_convert_enabled(bool(boxes))

    def _on_cell_det_error(self, msg: str) -> None:
        self._toolbar.set_cell_det_running(False)
        self._progress_bar.setVisible(False)
        QMessageBox.critical(self, "Detection Error", msg)

    def _on_cell_det_toggled(self, visible: bool) -> None:
        scene = self._view.scene()
        if isinstance(scene, SlideScene):
            scene.set_cell_det_visible(visible)

    def _cell_det_to_annot(self) -> None:
        if not self._cell_det_boxes or self._store is None:
            return
        markers_data = [
            (
                (x0 + x1) / 2.0,
                (y0 + y1) / 2.0,
                self._active_channel,
                x1 - x0,
                y1 - y0,
            )
            for x0, y0, x1, y1 in self._cell_det_boxes
        ]
        self._store.add_marker_batch(markers_data)
        self._update_undo_redo_state()

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
            self._save_to_db()
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
        self._agent_panel.shutdown()
        if self._reader:
            self._reader.close()
        if self._db:
            self._db.close()
        if self._eval_db:
            self._eval_db.close()
        event.accept()
