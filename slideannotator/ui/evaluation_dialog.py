"""Dialogs for the model-evaluation feature.

``EvaluationSelectionDialog`` lets the user pick markers, images and an IoU
threshold before running an evaluation.  ``EvaluationResultsDialog`` renders the
resulting per-marker metrics.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QRadioButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..inference.evaluation import EvaluationResult, precision_recall_f1

_DIALOG_STYLE = (
    "QDialog { background: #1e1e1e; }"
    "QLabel { color: #ccc; font-size: 12px; }"
    "QCheckBox { color: #ccc; font-size: 12px; spacing: 6px; }"
    "QCheckBox::indicator { width: 14px; height: 14px; }"
    "QRadioButton { color: #ccc; font-size: 12px; }"
    "QRadioButton:disabled { color: #666; }"
    "QDoubleSpinBox { background: #2a2a2a; color: #ccc; border: 1px solid #444;"
    "  border-radius: 3px; padding: 2px 4px; }"
    "QDialogButtonBox QPushButton {"
    "  background: #2e2e2e; color: #ccc;"
    "  border: 1px solid #444; border-radius: 4px; padding: 4px 16px;"
    "}"
    "QDialogButtonBox QPushButton:hover { background: #3a3a3a; }"
    "QDialogButtonBox QPushButton:disabled { color: #555; }"
)


class _CheckList(QWidget):
    """A titled, scrollable list of checkboxes with a select-all toggle."""

    def __init__(self, title: str, items: list[str], parent=None) -> None:
        super().__init__(parent)
        self._checkboxes: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QLabel(title)
        header.setStyleSheet("color: #ddd; font-size: 12px; font-weight: bold;")
        layout.addWidget(header)

        self._select_all_cb = QCheckBox("Select / deselect all")
        self._select_all_cb.setTristate(False)
        self._select_all_cb.setStyleSheet(
            "QCheckBox { color: #999; font-size: 11px; font-style: italic; }"
        )
        self._select_all_cb.stateChanged.connect(self._on_select_all_changed)
        layout.addWidget(self._select_all_cb)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #3a3a3a;")
        layout.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(4)
        inner_layout.setContentsMargins(4, 4, 4, 4)
        for name in items:
            cb = QCheckBox(name)
            cb.setChecked(True)
            cb.stateChanged.connect(self._on_item_changed)
            self._checkboxes[name] = cb
            inner_layout.addWidget(cb)
        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        # Start with all selected.
        self._select_all_cb.setCheckState(Qt.CheckState.Checked)

    def selected(self) -> list[str]:
        return [name for name, cb in self._checkboxes.items() if cb.isChecked()]

    def _on_select_all_changed(self, state: int) -> None:
        checked = state == Qt.CheckState.Checked.value
        for cb in self._checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(checked)
            cb.blockSignals(False)

    def _on_item_changed(self) -> None:
        states = [cb.isChecked() for cb in self._checkboxes.values()]
        self._select_all_cb.blockSignals(True)
        if states and all(states):
            self._select_all_cb.setCheckState(Qt.CheckState.Checked)
        elif any(states):
            self._select_all_cb.setCheckState(Qt.CheckState.PartiallyChecked)
        else:
            self._select_all_cb.setCheckState(Qt.CheckState.Unchecked)
        self._select_all_cb.blockSignals(False)


class EvaluationSelectionDialog(QDialog):
    """Popup to choose markers, images and IoU threshold for an evaluation."""

    def __init__(
        self,
        markers: list[str],
        images: list[str],
        seg_available: bool = False,
        default_iou: float = 0.3,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Evaluate Model")
        self.setMinimumSize(480, 420)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 12, 14, 14)

        # Two side-by-side check lists: markers | images.
        lists_row = QHBoxLayout()
        lists_row.setSpacing(12)
        self._marker_list = _CheckList("Markers", markers)
        self._image_list = _CheckList("Images", images)
        lists_row.addWidget(self._marker_list, 1)
        lists_row.addWidget(self._image_list, 1)
        layout.addLayout(lists_row, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #3a3a3a;")
        layout.addWidget(sep)

        # Task type — segmentation is disabled until a seg model is configured.
        task_row = QHBoxLayout()
        task_row.addWidget(QLabel("Task:"))
        self._detection_radio = QRadioButton("Object detection")
        self._detection_radio.setChecked(True)
        self._segmentation_radio = QRadioButton("Semantic segmentation")
        self._segmentation_radio.setEnabled(seg_available)
        if not seg_available:
            self._segmentation_radio.setToolTip(
                "No segmentation model configured (set seg_model in settings.yaml)."
            )
        task_group = QButtonGroup(self)
        task_group.addButton(self._detection_radio)
        task_group.addButton(self._segmentation_radio)
        task_row.addWidget(self._detection_radio)
        task_row.addWidget(self._segmentation_radio)
        task_row.addStretch()
        layout.addLayout(task_row)

        # IoU threshold.
        iou_row = QHBoxLayout()
        self._iou_label = QLabel("IoU threshold:")
        self._iou_spin = QDoubleSpinBox()
        self._iou_spin.setRange(0.05, 0.95)
        self._iou_spin.setSingleStep(0.05)
        self._iou_spin.setDecimals(2)
        self._iou_spin.setValue(default_iou)
        iou_row.addWidget(self._iou_label)
        iou_row.addWidget(self._iou_spin)
        iou_row.addStretch()
        layout.addLayout(iou_row)

        # The IoU threshold only applies to detection.
        self._detection_radio.toggled.connect(self._on_task_changed)
        self._on_task_changed()

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Evaluate")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_task_changed(self) -> None:
        is_detection = self._detection_radio.isChecked()
        self._iou_label.setEnabled(is_detection)
        self._iou_spin.setEnabled(is_detection)

    def selected_markers(self) -> list[str]:
        return self._marker_list.selected()

    def selected_images(self) -> list[str]:
        return self._image_list.selected()

    def iou_threshold(self) -> float:
        return self._iou_spin.value()

    def task_type(self) -> str:
        return "segmentation" if self._segmentation_radio.isChecked() else "detection"


class EvaluationResultsDialog(QDialog):
    """Renders per-marker and overall evaluation metrics in a table."""

    def __init__(self, result: EvaluationResult, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Evaluation Results")
        self.setMinimumSize(560, 360)
        self.setStyleSheet(
            "QDialog { background: #1e1e1e; }"
            "QLabel { color: #ccc; font-size: 12px; }"
            "QTableWidget { background: #222; color: #ccc; gridline-color: #3a3a3a;"
            "  border: 1px solid #3a3a3a; }"
            "QHeaderView::section { background: #2a2a2a; color: #ddd; border: none;"
            "  padding: 4px; font-weight: bold; }"
            "QTableWidget::item { padding: 3px; }"
            "QDialogButtonBox QPushButton {"
            "  background: #2e2e2e; color: #ccc;"
            "  border: 1px solid #444; border-radius: 4px; padding: 4px 16px;"
            "}"
            "QDialogButtonBox QPushButton:hover { background: #3a3a3a; }"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 12, 14, 14)

        if result.task == "segmentation":
            header = "Semantic segmentation"
        else:
            header = f"Object detection  ·  IoU ≥ {result.iou_threshold:.2f}"
        title = QLabel(header)
        title.setStyleSheet("color: #ddd; font-size: 13px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel(f"{result.n_slides} image(s)  ·  {result.total_fovs} FOV evaluation(s)")
        subtitle.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(subtitle)

        table = QTableWidget()
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.verticalHeader().setVisible(False)
        if result.task == "segmentation":
            self._fill_segmentation(table, result)
        else:
            self._fill_detection(table, result)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table, 1)

        if result.skipped_slides:
            warn = QLabel("Skipped (file not found): " + ", ".join(result.skipped_slides))
            warn.setStyleSheet("color: #d08a2a; font-size: 11px;")
            warn.setWordWrap(True)
            layout.addWidget(warn)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        btns.accepted.connect(self.accept)
        btns.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        layout.addWidget(btns)

    # ------------------------------------------------------------------
    def _fill_detection(self, table: QTableWidget, result: EvaluationResult) -> None:
        headers = ["Marker", "TP", "FP", "FN", "Precision", "Recall", "F1", "FOVs"]
        markers = sorted(result.detection)
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(markers) + 1)

        for row, marker in enumerate(markers):
            r = result.detection[marker]
            self._set_row(
                table,
                row,
                [
                    marker,
                    str(r.tp),
                    str(r.fp),
                    str(r.fn),
                    f"{r.precision:.3f}",
                    f"{r.recall:.3f}",
                    f"{r.f1:.3f}",
                    str(r.n_fovs),
                ],
            )

        tp, fp, fn = result.overall_detection()
        p, rec, f1 = precision_recall_f1(tp, fp, fn)
        total_fovs = sum(r.n_fovs for r in result.detection.values())
        self._set_row(
            table,
            len(markers),
            [
                "OVERALL",
                str(tp),
                str(fp),
                str(fn),
                f"{p:.3f}",
                f"{rec:.3f}",
                f"{f1:.3f}",
                str(total_fovs),
            ],
            bold=True,
        )

    def _fill_segmentation(self, table: QTableWidget, result: EvaluationResult) -> None:
        headers = ["Marker", "Mean Dice", "Mean Accuracy", "FOVs"]
        markers = sorted(result.segmentation)
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(markers) + 1)

        for row, marker in enumerate(markers):
            r = result.segmentation[marker]
            self._set_row(
                table,
                row,
                [marker, f"{r.mean_dice:.3f}", f"{r.mean_accuracy:.3f}", str(r.n_fovs)],
            )

        mean_dice, mean_acc = result.overall_segmentation()
        total_fovs = sum(r.n_fovs for r in result.segmentation.values())
        self._set_row(
            table,
            len(markers),
            ["OVERALL", f"{mean_dice:.3f}", f"{mean_acc:.3f}", str(total_fovs)],
            bold=True,
        )

    @staticmethod
    def _set_row(table: QTableWidget, row: int, values: list[str], bold: bool = False) -> None:
        from PySide6.QtGui import QFont

        for col, text in enumerate(values):
            item = QTableWidgetItem(text)
            if col > 0:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if bold:
                font = item.font()
                font.setWeight(QFont.Weight.Bold)
                item.setFont(font)
            table.setItem(row, col, item)
