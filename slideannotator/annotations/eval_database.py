"""SQLite store for model-evaluation results.

Kept separate from the annotation database so evaluation history has its own
lifecycle.  One *model* (identified by name + type) can accumulate many
*evaluations* (e.g. one image vs. all images), each of which stores per-marker
and overall *metrics*.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ..inference.evaluation import EvaluationResult, precision_recall_f1

OVERALL_MARKER = "__overall__"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS models (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    model_type TEXT NOT NULL,
    UNIQUE(name, model_type)
);

CREATE TABLE IF NOT EXISTS evaluations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id      INTEGER NOT NULL,
    created_at    TEXT NOT NULL,
    iou_threshold REAL,
    n_slides      INTEGER NOT NULL DEFAULT 0,
    n_fovs        INTEGER NOT NULL DEFAULT 0,
    images        TEXT NOT NULL DEFAULT '',
    markers       TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evaluation_metrics (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id INTEGER NOT NULL,
    marker        TEXT NOT NULL,
    is_overall    INTEGER NOT NULL DEFAULT 0,
    tp            INTEGER,
    fp            INTEGER,
    fn            INTEGER,
    precision     REAL,
    recall        REAL,
    f1            REAL,
    mean_dice     REAL,
    mean_accuracy REAL,
    n_fovs        INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (evaluation_id) REFERENCES evaluations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_eval_model ON evaluations(model_id);
CREATE INDEX IF NOT EXISTS idx_metric_eval ON evaluation_metrics(evaluation_id);
"""


@dataclass
class MetricRow:
    marker: str
    is_overall: bool = False
    tp: int | None = None
    fp: int | None = None
    fn: int | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    mean_dice: float | None = None
    mean_accuracy: float | None = None
    n_fovs: int = 0


@dataclass
class EvaluationRecord:
    id: int
    model_name: str
    model_type: str
    created_at: str
    iou_threshold: float | None
    n_slides: int
    n_fovs: int
    images: list[str] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)
    metrics: list[MetricRow] = field(default_factory=list)

    def overall(self) -> MetricRow | None:
        for m in self.metrics:
            if m.is_overall:
                return m
        return None

    def marker_metric(self, marker: str) -> MetricRow | None:
        for m in self.metrics:
            if not m.is_overall and m.marker == marker:
                return m
        return None


class EvaluationDB:
    """SQLite-backed evaluation-history store."""

    def __init__(self, db_path: Path) -> None:
        db_path = db_path.expanduser().resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------------
    def _get_or_create_model(self, name: str, model_type: str) -> int:
        cur = self._conn.execute(
            "SELECT id FROM models WHERE name = ? AND model_type = ?", (name, model_type)
        )
        row = cur.fetchone()
        if row is not None:
            return int(row[0])
        cur = self._conn.execute(
            "INSERT INTO models (name, model_type) VALUES (?, ?)", (name, model_type)
        )
        return int(cur.lastrowid)

    def save_evaluation(self, result: EvaluationResult, model_name: str) -> int:
        """Persist an :class:`EvaluationResult`. Returns the new evaluation id."""
        model_id = self._get_or_create_model(model_name, result.task)
        now = datetime.now(UTC).isoformat()
        iou = result.iou_threshold if result.task == "detection" else None

        cur = self._conn.execute(
            "INSERT INTO evaluations "
            "(model_id, created_at, iou_threshold, n_slides, n_fovs, images, markers) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                model_id,
                now,
                iou,
                result.n_slides,
                result.total_fovs,
                ",".join(result.images),
                ",".join(result.markers),
            ),
        )
        eval_id = int(cur.lastrowid)

        rows = self._metric_rows_from_result(result)
        self._conn.executemany(
            "INSERT INTO evaluation_metrics "
            "(evaluation_id, marker, is_overall, tp, fp, fn, precision, recall, f1, "
            " mean_dice, mean_accuracy, n_fovs) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    eval_id,
                    r.marker,
                    int(r.is_overall),
                    r.tp,
                    r.fp,
                    r.fn,
                    r.precision,
                    r.recall,
                    r.f1,
                    r.mean_dice,
                    r.mean_accuracy,
                    r.n_fovs,
                )
                for r in rows
            ],
        )
        self._conn.commit()
        return eval_id

    @staticmethod
    def _metric_rows_from_result(result: EvaluationResult) -> list[MetricRow]:
        rows: list[MetricRow] = []
        if result.task == "segmentation":
            for marker in sorted(result.segmentation):
                r = result.segmentation[marker]
                rows.append(
                    MetricRow(
                        marker=marker,
                        mean_dice=r.mean_dice,
                        mean_accuracy=r.mean_accuracy,
                        n_fovs=r.n_fovs,
                    )
                )
            mean_dice, mean_acc = result.overall_segmentation()
            rows.append(
                MetricRow(
                    marker=OVERALL_MARKER,
                    is_overall=True,
                    mean_dice=mean_dice,
                    mean_accuracy=mean_acc,
                    n_fovs=sum(r.n_fovs for r in result.segmentation.values()),
                )
            )
        else:
            for marker in sorted(result.detection):
                r = result.detection[marker]
                rows.append(
                    MetricRow(
                        marker=marker,
                        tp=r.tp,
                        fp=r.fp,
                        fn=r.fn,
                        precision=r.precision,
                        recall=r.recall,
                        f1=r.f1,
                        n_fovs=r.n_fovs,
                    )
                )
            tp, fp, fn = result.overall_detection()
            p, rec, f1 = precision_recall_f1(tp, fp, fn)
            rows.append(
                MetricRow(
                    marker=OVERALL_MARKER,
                    is_overall=True,
                    tp=tp,
                    fp=fp,
                    fn=fn,
                    precision=p,
                    recall=rec,
                    f1=f1,
                    n_fovs=sum(r.n_fovs for r in result.detection.values()),
                )
            )
        return rows

    # ------------------------------------------------------------------
    def get_evaluations(self) -> list[EvaluationRecord]:
        """Return all evaluations, newest first, with their metric rows."""
        eval_rows = self._conn.execute(
            "SELECT e.id, m.name, m.model_type, e.created_at, e.iou_threshold, "
            "       e.n_slides, e.n_fovs, e.images, e.markers "
            "FROM evaluations e JOIN models m ON e.model_id = m.id "
            "ORDER BY e.created_at DESC, e.id DESC"
        ).fetchall()

        records: list[EvaluationRecord] = []
        for (
            eval_id,
            model_name,
            model_type,
            created_at,
            iou_threshold,
            n_slides,
            n_fovs,
            images,
            markers,
        ) in eval_rows:
            metric_rows = self._conn.execute(
                "SELECT marker, is_overall, tp, fp, fn, precision, recall, f1, "
                "       mean_dice, mean_accuracy, n_fovs "
                "FROM evaluation_metrics WHERE evaluation_id = ? "
                "ORDER BY is_overall, marker",
                (eval_id,),
            ).fetchall()
            metrics = [
                MetricRow(
                    marker=mr[0],
                    is_overall=bool(mr[1]),
                    tp=mr[2],
                    fp=mr[3],
                    fn=mr[4],
                    precision=mr[5],
                    recall=mr[6],
                    f1=mr[7],
                    mean_dice=mr[8],
                    mean_accuracy=mr[9],
                    n_fovs=mr[10],
                )
                for mr in metric_rows
            ]
            records.append(
                EvaluationRecord(
                    id=eval_id,
                    model_name=model_name,
                    model_type=model_type,
                    created_at=created_at,
                    iou_threshold=iou_threshold,
                    n_slides=n_slides,
                    n_fovs=n_fovs,
                    images=images.split(",") if images else [],
                    markers=markers.split(",") if markers else [],
                    metrics=metrics,
                )
            )
        return records

    def close(self) -> None:
        self._conn.close()
