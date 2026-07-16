"""Dialog that lists stored model evaluations in a single table.

Each row is one evaluation (a model at a point in time, over a set of images);
leading columns describe the run and the remaining columns hold the per-marker
and overall score.  Detection rows show F1, segmentation rows show mean Dice;
the full metric breakdown is available as a per-cell tooltip.

The table is interactive: click a header to sort, use the *Columns* menu to
hide/unhide columns, filter with the model-name box and the time-range selector,
and right-click a row (or press the *Delete Selected* button) to permanently
remove an evaluation from the database.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..annotations.eval_database import EvaluationDB, EvaluationRecord, MetricRow

_META_COLUMNS = ["Model", "Type", "Date", "Images", "FOVs", "IoU"]
_OVERALL_COLUMN = "OVERALL"

# Role used to stash per-row data on the first cell so it survives sorting.
_ID_ROLE = Qt.ItemDataRole.UserRole + 1
_CREATED_ROLE = Qt.ItemDataRole.UserRole + 2

# (label, max age) — None means "no limit".
_TIME_RANGES: list[tuple[str, timedelta | None]] = [
    ("All time", None),
    ("Last 24 hours", timedelta(days=1)),
    ("Last 7 days", timedelta(days=7)),
    ("Last 30 days", timedelta(days=30)),
    ("Last year", timedelta(days=365)),
]


def _format_date(created_at: str) -> str:
    try:
        dt = datetime.fromisoformat(created_at)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return created_at


def _parse_created(created_at: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(created_at)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


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


class _SortableItem(QTableWidgetItem):
    """Table item that sorts by a stored key rather than its display text."""

    def __init__(self, text: str, sort_key: float | str | None) -> None:
        super().__init__(text)
        self._sort_key = sort_key

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, _SortableItem):
            a, b = self._sort_key, other._sort_key
            if a is None:
                return b is not None
            if b is None:
                return False
            return a < b
        return super().__lt__(other)


class EvaluationsTableDialog(QDialog):
    """Interactive table of all stored evaluations."""

    def __init__(
        self,
        records: list[EvaluationRecord],
        db: EvaluationDB | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self.setWindowTitle("Model Evaluations")
        self.resize(1000, 520)
        self.setStyleSheet(
            "QDialog { background: #1e1e1e; }"
            "QLabel { color: #ccc; font-size: 12px; }"
            "QLineEdit, QComboBox { background: #2a2a2a; color: #ddd;"
            "  border: 1px solid #444; border-radius: 4px; padding: 3px 6px; }"
            "QTableWidget { background: #222; color: #ccc; gridline-color: #3a3a3a;"
            "  border: 1px solid #3a3a3a; }"
            "QHeaderView::section { background: #2a2a2a; color: #ddd; border: none;"
            "  padding: 4px; font-weight: bold; }"
            "QTableWidget::item { padding: 3px; }"
            "QTableWidget::item:selected { background: #2a4a7a; }"
            "QPushButton {"
            "  background: #2e2e2e; color: #ccc;"
            "  border: 1px solid #444; border-radius: 4px; padding: 4px 16px;"
            "}"
            "QPushButton:hover { background: #3a3a3a; }"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 12, 14, 14)

        self._table: QTableWidget | None = None
        self._headers: list[str] = []

        if not records:
            layout.addWidget(QLabel("No evaluations have been run yet."))
        else:
            note = QLabel(
                "Cell value = F1 (detection) or mean Dice (segmentation). "
                "Click a header to sort; hover a cell for details."
            )
            note.setStyleSheet("color: #999; font-size: 11px;")
            layout.addWidget(note)
            layout.addLayout(self._build_controls())
            self._table = self._build_table(records)
            layout.addWidget(self._table, 1)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        layout.addWidget(btns)

    # ------------------------------------------------------------------
    def _build_controls(self):
        row = QHBoxLayout()
        row.setSpacing(8)

        self._name_filter = QLineEdit()
        self._name_filter.setPlaceholderText("Filter by model name…")
        self._name_filter.setClearButtonEnabled(True)
        self._name_filter.textChanged.connect(self._apply_filters)
        row.addWidget(self._name_filter, 1)

        self._time_filter = QComboBox()
        for label, _ in _TIME_RANGES:
            self._time_filter.addItem(label)
        self._time_filter.currentIndexChanged.connect(self._apply_filters)
        row.addWidget(QLabel("Time:"))
        row.addWidget(self._time_filter)

        self._columns_btn = QPushButton("Columns ▾")
        self._columns_menu = QMenu(self._columns_btn)
        self._columns_btn.setMenu(self._columns_menu)
        row.addWidget(self._columns_btn)

        self._delete_btn = QPushButton("Delete Selected")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._delete_selected)
        row.addWidget(self._delete_btn)

        return row

    def _build_columns_menu(self) -> None:
        self._columns_menu.clear()
        for col, header in enumerate(self._headers):
            action = self._columns_menu.addAction(header)
            action.setCheckable(True)
            action.setChecked(not self._table.isColumnHidden(col))
            action.toggled.connect(
                lambda checked, c=col: self._table.setColumnHidden(c, not checked)
            )

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
        self._markers = markers

        self._headers = _META_COLUMNS + markers + [_OVERALL_COLUMN]
        table = QTableWidget()
        table.setColumnCount(len(self._headers))
        table.setHorizontalHeaderLabels(self._headers)
        table.setRowCount(len(records))
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSortingEnabled(True)
        table.verticalHeader().setVisible(False)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(self._show_context_menu)
        table.itemSelectionChanged.connect(self._on_selection_changed)

        # Populate with sorting disabled to keep row/record alignment.
        table.setSortingEnabled(False)
        for row, rec in enumerate(records):
            self._fill_row(table, row, rec, markers)
        table.setSortingEnabled(True)

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSortIndicator(2, Qt.SortOrder.DescendingOrder)

        self._table = table
        self._build_columns_menu()
        return table

    def _fill_row(
        self, table: QTableWidget, row: int, rec: EvaluationRecord, markers: list[str]
    ) -> None:
        iou_text = "—" if rec.iou_threshold is None else f"{rec.iou_threshold:.2f}"
        iou_key = None if rec.iou_threshold is None else float(rec.iou_threshold)
        type_text = "Segmentation" if rec.model_type == "segmentation" else "Detection"

        model_item = QTableWidgetItem(rec.model_name)
        model_item.setData(_ID_ROLE, rec.id)
        model_item.setData(_CREATED_ROLE, rec.created_at)

        images_item = _SortableItem(str(len(rec.images)), len(rec.images))
        if rec.images:
            images_item.setToolTip("\n".join(rec.images))

        meta_items = [
            model_item,
            QTableWidgetItem(type_text),
            _SortableItem(_format_date(rec.created_at), rec.created_at),
            images_item,
            _SortableItem(str(rec.n_fovs), rec.n_fovs),
            _SortableItem(iou_text, iou_key),
        ]
        for col, item in enumerate(meta_items):
            if col != 0:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, col, item)

        base = len(_META_COLUMNS)
        for i, marker in enumerate(markers):
            metric = rec.marker_metric(marker)
            score = _primary_score(rec, metric)
            item = _SortableItem(score, float(score) if score else None)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tip = _metric_tooltip(rec, metric)
            if tip:
                item.setToolTip(tip)
            table.setItem(row, base + i, item)

        overall = rec.overall()
        overall_score = _primary_score(rec, overall)
        overall_item = _SortableItem(overall_score, float(overall_score) if overall_score else None)
        overall_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        tip = _metric_tooltip(rec, overall)
        if tip:
            overall_item.setToolTip(tip)
        font = overall_item.font()
        font.setBold(True)
        overall_item.setFont(font)
        table.setItem(row, base + len(markers), overall_item)

    # ------------------------------------------------------------------
    def _apply_filters(self) -> None:
        if self._table is None:
            return
        name_query = self._name_filter.text().strip().lower()
        max_age = _TIME_RANGES[self._time_filter.currentIndex()][1]
        cutoff = datetime.now(UTC) - max_age if max_age is not None else None

        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item is None:
                continue
            visible = True
            if name_query and name_query not in item.text().lower():
                visible = False
            if visible and cutoff is not None:
                created = _parse_created(item.data(_CREATED_ROLE))
                if created is None or created < cutoff:
                    visible = False
            self._table.setRowHidden(row, not visible)

    # ------------------------------------------------------------------
    def _on_selection_changed(self) -> None:
        self._delete_btn.setEnabled(bool(self._selected_rows()))

    def _selected_rows(self) -> list[int]:
        if self._table is None:
            return []
        return sorted({idx.row() for idx in self._table.selectionModel().selectedRows()})

    def _show_context_menu(self, pos) -> None:
        if self._table is None:
            return
        menu = QMenu(self._table)
        delete_action = menu.addAction("Delete evaluation(s)…")
        delete_action.setEnabled(bool(self._selected_rows()))
        chosen = menu.exec(self._table.viewport().mapToGlobal(pos))
        if chosen is delete_action:
            self._delete_selected()

    def _delete_selected(self) -> None:
        rows = self._selected_rows()
        if not rows or self._table is None:
            return
        if self._db is None:
            QMessageBox.warning(
                self,
                "Cannot Delete",
                "No database is available to delete evaluations from.",
            )
            return

        count = len(rows)
        confirm = QMessageBox.question(
            self,
            "Delete Evaluations",
            f"Permanently delete {count} evaluation{'s' if count != 1 else ''}? "
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        # Collect ids first, then remove rows bottom-up so indices stay valid.
        to_delete: list[tuple[int, int]] = []
        for row in rows:
            item = self._table.item(row, 0)
            if item is None:
                continue
            to_delete.append((row, int(item.data(_ID_ROLE))))

        for row, eval_id in sorted(to_delete, reverse=True):
            try:
                self._db.delete_evaluation(eval_id)
            except Exception as exc:  # pragma: no cover - defensive
                QMessageBox.warning(self, "Delete Failed", str(exc))
                return
            self._table.removeRow(row)

        self._on_selection_changed()
