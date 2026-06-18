from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
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

from slideannotator.settings import Settings

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
    "QScrollArea { border: none; background: #222; }"
    "QScrollBar:vertical { background: #2a2a2a; width: 8px; }"
    "QScrollBar::handle:vertical { background: #555; border-radius: 4px; }"
    "QDialogButtonBox QPushButton { padding: 4px 12px; }"
)


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
        self._cell_det_model_edit = self._path_row(
            form,
            "Cell detection model:",
            str(self._settings.cell_det_model or ""),
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

        cd_text = self._cell_det_model_edit.text().strip()
        s.cell_det_model = Path(cd_text).expanduser() if cd_text else None

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
