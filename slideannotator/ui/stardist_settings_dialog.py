from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from slideannotator.settings import CellDetModelConfig, Settings

_STYLE = (
    "QDialog { background: #222; color: #ccc; }"
    "QGroupBox { color: #aaa; border: 1px solid #444; border-radius: 6px;"
    "  margin-top: 8px; padding-top: 8px; }"
    "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;"
    "  padding: 0 4px; left: 8px; }"
    "QLabel { color: #ccc; }"
    "QLineEdit { background: #2a2a2a; color: #ccc; border: 1px solid #444;"
    "  border-radius: 4px; padding: 2px 4px; }"
    "QSpinBox { background: #2a2a2a; color: #ccc; border: 1px solid #444;"
    "  border-radius: 4px; padding: 2px 4px; }"
    "QSpinBox::up-button, QSpinBox::down-button { background: #333; }"
    "QPushButton { background: #2e2e2e; color: #ccc; border: 1px solid #444;"
    "  border-radius: 4px; padding: 3px 8px; }"
    "QPushButton:hover { background: #3a3a3a; }"
    "QComboBox { background: #2a2a2a; color: #ccc; border: 1px solid #444;"
    "  border-radius: 4px; padding: 2px 4px; }"
    "QComboBox QAbstractItemView { background: #2a2a2a; color: #ccc;"
    "  selection-background-color: #3a3a3a; }"
    "QScrollArea { border: none; background: #222; }"
    "QScrollBar:vertical { background: #2a2a2a; width: 8px; }"
    "QScrollBar::handle:vertical { background: #555; border-radius: 4px; }"
    "QDialogButtonBox QPushButton { padding: 4px 12px; }"
)


class _CellDetModelRow(QWidget):
    """One editable row: model path, normalization scheme, and default flag."""

    default_toggled = Signal(object)  # emits self when checked
    remove_requested = Signal(object)  # emits self

    def __init__(self, model: CellDetModelConfig | None, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.path_edit = QLineEdit(str(model.path) if model else "")
        self.path_edit.setPlaceholderText("Path to .onnx model")
        browse = QPushButton("Browse…")
        browse.setFixedWidth(72)
        browse.clicked.connect(self._browse)

        self.norm_combo = QComboBox()
        self.norm_combo.addItems(["imagenet", "none"])
        idx = self.norm_combo.findText(model.norm) if model else -1
        self.norm_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.norm_combo.setToolTip(
            "RF-DETR normalization: 'imagenet' (0-1 scale + ImageNet mean/std) or "
            "'none' (16-bit 0-1 scale only). Ignored by D-FINE/RT-DETR."
        )

        self.default_check = QCheckBox("Default")
        self.default_check.setChecked(bool(model and model.default))
        self.default_check.toggled.connect(self._on_default_toggled)

        remove_btn = QPushButton("✕")
        remove_btn.setFixedWidth(28)
        remove_btn.setToolTip("Remove model")
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))

        layout.addWidget(self.path_edit, 1)
        layout.addWidget(browse)
        layout.addWidget(self.norm_combo)
        layout.addWidget(self.default_check)
        layout.addWidget(remove_btn)

    def _browse(self) -> None:
        start = self.path_edit.text() or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "Select Model", start, "ONNX models (*.onnx)")
        if path:
            self.path_edit.setText(path)

    def _on_default_toggled(self, checked: bool) -> None:
        if checked:
            self.default_toggled.emit(self)

    def to_config(self) -> CellDetModelConfig | None:
        text = self.path_edit.text().strip()
        if not text:
            return None
        return CellDetModelConfig(
            path=Path(text).expanduser(),
            norm=self.norm_combo.currentText(),
            default=self.default_check.isChecked(),
        )


class _CellDetModelsEditor(QWidget):
    """Add/remove/edit rows for the registered cell-detection models."""

    def __init__(self, models: list[CellDetModelConfig], parent=None) -> None:
        super().__init__(parent)
        self._rows: list[_CellDetModelRow] = []

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setSpacing(4)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        outer.addLayout(self._rows_layout)

        add_btn = QPushButton("+ Add Model")
        add_btn.clicked.connect(lambda: self._add_row(None))
        outer.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        for model in models:
            self._add_row(model)
        if not models:
            self._add_row(None)

    def _add_row(self, model: CellDetModelConfig | None) -> None:
        row = _CellDetModelRow(model)
        row.remove_requested.connect(self._remove_row)
        row.default_toggled.connect(self._on_row_default)
        self._rows.append(row)
        self._rows_layout.addWidget(row)

    def _remove_row(self, row: _CellDetModelRow) -> None:
        if row not in self._rows:
            return
        self._rows.remove(row)
        self._rows_layout.removeWidget(row)
        row.deleteLater()

    def _on_row_default(self, checked_row: _CellDetModelRow) -> None:
        for row in self._rows:
            if row is not checked_row:
                row.default_check.blockSignals(True)
                row.default_check.setChecked(False)
                row.default_check.blockSignals(False)

    def models(self) -> list[CellDetModelConfig]:
        configs = [row.to_config() for row in self._rows]
        return [cfg for cfg in configs if cfg is not None]


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setStyleSheet(_STYLE)

        self._settings = settings
        self._outline_color = QColor(*settings.outline_color)
        self._detections_color = QColor(*settings.detections_color)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(12)
        inner_layout.setContentsMargins(8, 8, 8, 8)
        inner_layout.addWidget(self._build_paths_group())
        inner_layout.addWidget(self._build_stardist_group())
        inner_layout.addWidget(self._build_regions_group())
        inner_layout.addWidget(self._build_cell_det_models_group())
        inner_layout.addWidget(self._build_cell_det_group())
        inner_layout.addWidget(self._build_fov_group())
        inner_layout.addStretch()
        scroll.setWidget(inner)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)
        main_layout.addWidget(btns)

    # ------------------------------------------------------------------
    # Group builders
    # ------------------------------------------------------------------

    def _build_paths_group(self) -> QGroupBox:
        box = QGroupBox("Paths")
        form = QFormLayout(box)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._annotations_dir = self._path_row(
            form, "Annotations dir:", str(self._settings.annotations_dir), is_dir=True
        )
        self._db_path = self._path_row(
            form,
            "Database path:",
            str(self._settings.db_path),
            is_dir=False,
            file_filter="Database files (*.db *.sqlite)",
        )
        self._data_dir = self._path_row(
            form, "Data dir:", str(self._settings.data_dir or ""), is_dir=True
        )
        self._stardist_model_edit = self._path_row(
            form,
            "StarDist model:",
            str(self._settings.stardist_model or ""),
            is_dir=False,
            file_filter="ONNX models (*.onnx)",
        )
        return box

    def _build_stardist_group(self) -> QGroupBox:
        box = QGroupBox("StarDist Nucleus Outline")
        form = QFormLayout(box)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._outline_color_btn = QPushButton()
        self._outline_color_btn.setFixedSize(80, 26)
        self._outline_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_color_btn(self._outline_color_btn, self._outline_color)
        self._outline_color_btn.clicked.connect(self._pick_outline_color)
        form.addRow("Outline color:", self._outline_color_btn)

        self._outline_thickness = QSpinBox()
        self._outline_thickness.setRange(1, 10)
        self._outline_thickness.setValue(self._settings.outline_thickness)
        self._outline_thickness.setSuffix(" px")
        self._outline_thickness.setFixedWidth(80)
        form.addRow("Line thickness:", self._outline_thickness)

        return box

    def _build_regions_group(self) -> QGroupBox:
        box = QGroupBox("Regions")
        form = QFormLayout(box)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._region_opacity = QSpinBox()
        self._region_opacity.setRange(0, 100)
        self._region_opacity.setValue(self._settings.region_opacity)
        self._region_opacity.setSuffix(" %")
        self._region_opacity.setFixedWidth(80)
        form.addRow("Fill opacity:", self._region_opacity)

        return box

    def _build_cell_det_models_group(self) -> QGroupBox:
        box = QGroupBox("Cell Detection Models")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        self._cell_det_models_editor = _CellDetModelsEditor(self._settings.cell_det_models)
        layout.addWidget(self._cell_det_models_editor)
        return box

    def _build_cell_det_group(self) -> QGroupBox:
        box = QGroupBox("Cell Detection")
        form = QFormLayout(box)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._det_color_btn = QPushButton()
        self._det_color_btn.setFixedSize(80, 26)
        self._det_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_color_btn(self._det_color_btn, self._detections_color)
        self._det_color_btn.clicked.connect(self._pick_det_color)
        form.addRow("Detections color:", self._det_color_btn)

        return box

    def _build_fov_group(self) -> QGroupBox:
        box = QGroupBox("Field of View")
        form = QFormLayout(box)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        size_widget = QWidget()
        size_layout = QHBoxLayout(size_widget)
        size_layout.setContentsMargins(0, 0, 0, 0)
        size_layout.setSpacing(6)

        self._fov_width = QSpinBox()
        self._fov_width.setRange(64, 4096)
        self._fov_width.setValue(self._settings.fov_size[0])
        self._fov_width.setSuffix(" px")

        self._fov_height = QSpinBox()
        self._fov_height.setRange(64, 4096)
        self._fov_height.setValue(self._settings.fov_size[1])
        self._fov_height.setSuffix(" px")

        size_layout.addWidget(QLabel("W:"))
        size_layout.addWidget(self._fov_width)
        size_layout.addWidget(QLabel("H:"))
        size_layout.addWidget(self._fov_height)
        size_layout.addStretch()

        form.addRow("FOV size:", size_widget)
        return box

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _path_row(
        self,
        form: QFormLayout,
        label: str,
        value: str,
        is_dir: bool,
        file_filter: str = "",
    ) -> QLineEdit:
        edit = QLineEdit(value)
        edit.setPlaceholderText("(not set)")
        browse = QPushButton("Browse…")
        browse.setFixedWidth(72)
        browse.clicked.connect(lambda: self._browse(edit, is_dir, file_filter))

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)
        row_layout.addWidget(edit)
        row_layout.addWidget(browse)

        form.addRow(label, row_widget)
        return edit

    def _browse(self, edit: QLineEdit, is_dir: bool, file_filter: str) -> None:
        start = edit.text() or str(Path.home())
        if is_dir:
            path = QFileDialog.getExistingDirectory(self, "Select Directory", start)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select File", start, file_filter)
        if path:
            edit.setText(path)

    @staticmethod
    def _refresh_color_btn(btn: QPushButton, color: QColor) -> None:
        btn.setStyleSheet(
            f"background: {color.name()}; border: 1px solid #666; border-radius: 4px;"
        )

    def _pick_outline_color(self) -> None:
        c = QColorDialog.getColor(self._outline_color, self, "Choose Outline Color")
        if c.isValid():
            self._outline_color = c
            self._refresh_color_btn(self._outline_color_btn, c)

    def _pick_det_color(self) -> None:
        c = QColorDialog.getColor(self._detections_color, self, "Choose Detections Color")
        if c.isValid():
            self._detections_color = c
            self._refresh_color_btn(self._det_color_btn, c)

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------

    def get_settings(self) -> Settings:
        s = Settings()

        ann_text = self._annotations_dir.text().strip()
        s.annotations_dir = (
            Path(ann_text).expanduser() if ann_text else self._settings.annotations_dir
        )

        db_text = self._db_path.text().strip()
        s.db_path = Path(db_text).expanduser() if db_text else self._settings.db_path

        data_text = self._data_dir.text().strip()
        s.data_dir = Path(data_text).expanduser() if data_text else None

        sd_text = self._stardist_model_edit.text().strip()
        s.stardist_model = Path(sd_text).expanduser() if sd_text else None

        s.cell_det_models = self._cell_det_models_editor.models()

        s.outline_color = (
            self._outline_color.red(),
            self._outline_color.green(),
            self._outline_color.blue(),
        )
        s.outline_thickness = self._outline_thickness.value()
        s.region_opacity = self._region_opacity.value()
        s.detections_color = (
            self._detections_color.red(),
            self._detections_color.green(),
            self._detections_color.blue(),
        )
        s.fov_size = (self._fov_width.value(), self._fov_height.value())

        return s
