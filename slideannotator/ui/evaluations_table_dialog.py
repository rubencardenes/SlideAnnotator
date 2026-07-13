"""Dialog that lists stored model evaluations in a single table.

Each row is one evaluation (a model at a point in time, over a set of images);
leading columns describe the run and the remaining columns hold the per-marker
and overall score.  Detection rows show F1, segmentation rows show mean Dice;
the full metric breakdown is available as a per-cell tooltip.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..annotations.eval_database import EvaluationRecord, MetricRow

_META_COLUMNS = ["Model", "Type", "Date", "Images", "FOVs", "IoU"]
_OVERALL_COLUMN = "OVERALL"


def _format_date(created_at: str) -> str:
    try:
        dt = datetime.fromisoformat(created_at)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return created_at


def _primary_score(record: EvaluationRecord, metric: MetricRow | None) -> str:
    if metric is None:
        return ""
    if record.model_type == "segmentation":
        return "" if metric.mean_dice is None else f"{metric.mean_dice:.3f}"
    return "" if metric.f1 is None else f"{metric.f1:.3f}"


def _metric_tooltip(record: EvaluationRecord, metric: MetricRow | None) -> str:
    if metric is None:
        return ""
    if record.model_type == "segmentation":
        return (
            f"Mean Dice: {metric.mean_dice:.3f}\n"
            f"Mean Accuracy: {metric.mean_accuracy:.3f}\n"
            f"FOVs: {metric.n_fovs}"
        )
    return (
        f"Precision: {metric.precision:.3f}\n"
        f"Recall: {metric.recall:.3f}\n"
        f"F1: {metric.f1:.3f}\n"
        f"TP/FP/FN: {metric.tp}/{metric.fp}/{metric.fn}\n"
        f"FOVs: {metric.n_fovs}"
    )


class EvaluationsTableDialog(QDialog):
    """Read-only table of all stored evaluations."""

    def __init__(self, records: list[EvaluationRecord], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Model Evaluations")
        self.resize(1000, 520)
        self.setStyleSheet(
            "QDialog { background: #1e1e1e; }"
            "QLabel { color: #ccc; font-size: 12px; }"
            "QTableWidget { background: #222; color: #ccc; gridline-color: #3a3a3a;"
            "  border: 1px solid #3a3a3a; }"
            "QHeaderView::section { background: #2a2a2a; color: #ddd; border: none;"
            "  padding: 4px; font-weight: bold; }"
            "QTableWidget::item { padding: 3px; }"
            "QTableWidget::item:selected { background: #2a4a7a; }"
            "QDialogButtonBox QPushButton {"
            "  background: #2e2e2e; color: #ccc;"
            "  border: 1px solid #444; border-radius: 4px; padding: 4px 16px;"
            "}"
            "QDialogButtonBox QPushButton:hover { background: #3a3a3a; }"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 12, 14, 14)

        if not records:
            layout.addWidget(QLabel("No evaluations have been run yet."))
        else:
            note = QLabel(
                "Cell value = F1 (detection) or mean Dice (segmentation). Hover for details."
            )
            note.setStyleSheet("color: #999; font-size: 11px;")
            layout.addWidget(note)
            layout.addWidget(self._build_table(records), 1)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        layout.addWidget(btns)

    # ------------------------------------------------------------------
    def _build_table(self, records: list[EvaluationRecord]) -> QTableWidget:
        # Dynamic marker columns: union across all records, stable sorted order.
        markers: list[str] = []
        seen: set[str] = set()
        for rec in records:
            for marker in rec.markers:
                if marker not in seen:
                    seen.add(marker)
                    markers.append(marker)
        markers.sort()

        headers = _META_COLUMNS + markers + [_OVERALL_COLUMN]
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(records))
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)

        for row, rec in enumerate(records):
            self._fill_row(table, row, rec, markers)

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        return table

    def _fill_row(
        self, table: QTableWidget, row: int, rec: EvaluationRecord, markers: list[str]
    ) -> None:
        iou_text = "—" if rec.iou_threshold is None else f"{rec.iou_threshold:.2f}"
        type_text = "Segmentation" if rec.model_type == "segmentation" else "Detection"

        images_item = QTableWidgetItem(str(len(rec.images)))
        if rec.images:
            images_item.setToolTip("\n".join(rec.images))

        meta_items = [
            QTableWidgetItem(rec.model_name),
            QTableWidgetItem(type_text),
            QTableWidgetItem(_format_date(rec.created_at)),
            images_item,
            QTableWidgetItem(str(rec.n_fovs)),
            QTableWidgetItem(iou_text),
        ]
        for col, item in enumerate(meta_items):
            if col != 0:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, col, item)

        base = len(_META_COLUMNS)
        for i, marker in enumerate(markers):
            metric = rec.marker_metric(marker)
            item = QTableWidgetItem(_primary_score(rec, metric))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tip = _metric_tooltip(rec, metric)
            if tip:
                item.setToolTip(tip)
            table.setItem(row, base + i, item)

        overall = rec.overall()
        overall_item = QTableWidgetItem(_primary_score(rec, overall))
        overall_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        tip = _metric_tooltip(rec, overall)
        if tip:
            overall_item.setToolTip(tip)
        font = overall_item.font()
        font.setBold(True)
        overall_item.setFont(font)
        table.setItem(row, base + len(markers), overall_item)
