from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import AnnotationStore, CellMarker, FOVAnnotation, RegionAnnotation

_SCHEMA = """
CREATE TABLE IF NOT EXISTS slide_paths (
    slide_name TEXT PRIMARY KEY,
    slide_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS annotations (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    modified_at TEXT NOT NULL,
    created_by  TEXT NOT NULL DEFAULT '',
    slide_name  TEXT NOT NULL,
    color_r     INTEGER NOT NULL DEFAULT 255,
    color_g     INTEGER NOT NULL DEFAULT 255,
    color_b     INTEGER NOT NULL DEFAULT 255,
    biomarker   TEXT NOT NULL DEFAULT '',
    x           REAL,
    y           REAL,
    w           REAL,
    h           REAL
);

CREATE TABLE IF NOT EXISTS region_points (
    annotation_id TEXT NOT NULL,
    seq           INTEGER NOT NULL,
    px            REAL NOT NULL,
    py            REAL NOT NULL,
    PRIMARY KEY (annotation_id, seq),
    FOREIGN KEY (annotation_id) REFERENCES annotations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_annotations_slide ON annotations(slide_name);
"""

_INSERT = (
    "INSERT INTO annotations "
    "(id, type, created_at, modified_at, created_by, slide_name, "
    " color_r, color_g, color_b, biomarker, x, y, w, h) "
    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
)


class AnnotationDB:
    """SQLite-backed annotation store."""

    def __init__(self, db_path: Path) -> None:
        db_path = db_path.expanduser().resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------------
    def save_all(self, store: AnnotationStore, slide_name: str) -> int:
        """Replace all annotations for *slide_name* with the current store contents."""
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.cursor()
        cur.execute("DELETE FROM annotations WHERE slide_name = ?", (slide_name,))
        count = 0
        for ann in store.all_annotations():
            r, g, b = ann.color
            biomarker = getattr(ann, "channel", "")
            if isinstance(ann, RegionAnnotation):
                cur.execute(
                    _INSERT,
                    (ann.id, "region", ann.created_at, now, ann.created_by,
                     slide_name, r, g, b, biomarker, None, None, None, None),
                )
                cur.executemany(
                    "INSERT INTO region_points (annotation_id, seq, px, py) VALUES (?,?,?,?)",
                    [(ann.id, i, p[0], p[1]) for i, p in enumerate(ann.points)],
                )
            elif isinstance(ann, CellMarker):
                cur.execute(
                    _INSERT,
                    (ann.id, "cell_marker", ann.created_at, now, ann.created_by,
                     slide_name, r, g, b, biomarker, ann.x, ann.y, ann.w, ann.h),
                )
            elif isinstance(ann, FOVAnnotation):
                cur.execute(
                    _INSERT,
                    (ann.id, "fov", ann.created_at, now, ann.created_by,
                     slide_name, r, g, b, biomarker, ann.x, ann.y, ann.w, ann.h),
                )
            count += 1
        self._conn.commit()
        return count

    def load_for_slide(self, slide_name: str, store: AnnotationStore) -> int:
        """Load all annotations for *slide_name* into *store*. Clears the store first."""
        store.clear()
        rows = self._conn.execute(
            "SELECT id, type, created_at, modified_at, created_by, "
            "color_r, color_g, color_b, biomarker, x, y, w, h "
            "FROM annotations WHERE slide_name = ? ORDER BY created_at",
            (slide_name,),
        ).fetchall()
        count = 0
        for row in rows:
            ann_id, ann_type, created_at, modified_at, created_by, \
                cr, cg, cb, biomarker, x, y, w, h = row
            color = (cr or 255, cg or 255, cb or 255)
            meta = dict(
                created_at=created_at,
                modified_at=modified_at,
                created_by=created_by or "",
                color=color,
                slide_name=slide_name,
            )
            if ann_type == "cell_marker":
                ann: CellMarker | FOVAnnotation | RegionAnnotation = CellMarker(
                    id=ann_id, x=x, y=y, channel=biomarker,
                    w=w or 10.0, h=h or 10.0, **meta,
                )
            elif ann_type == "fov":
                ann = FOVAnnotation(
                    id=ann_id, x=x, y=y, w=w or 512.0, h=h or 512.0,
                    channel=biomarker, **meta,
                )
            elif ann_type == "region":
                pts = self._conn.execute(
                    "SELECT px, py FROM region_points "
                    "WHERE annotation_id = ? ORDER BY seq",
                    (ann_id,),
                ).fetchall()
                ann = RegionAnnotation(
                    id=ann_id, points=[(p[0], p[1]) for p in pts],
                    channel=biomarker, **meta,
                )
            else:
                continue
            store._load_annotation(ann)
            count += 1
        store.set_dirty(False)
        return count

    def record_slide_path(self, slide_name: str, slide_path: Path) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO slide_paths (slide_name, slide_path) VALUES (?,?)",
            (slide_name, str(slide_path)),
        )
        self._conn.commit()

    def get_slide_paths(self) -> dict[str, Path | None]:
        """Return {slide_name: Path} for every slide that has annotations.

        Path is None when the slide file location was never recorded.
        """
        rows = self._conn.execute(
            "SELECT a.slide_name, p.slide_path "
            "FROM (SELECT DISTINCT slide_name FROM annotations) a "
            "LEFT JOIN slide_paths p ON a.slide_name = p.slide_name "
            "ORDER BY a.slide_name"
        ).fetchall()
        return {row[0]: Path(row[1]) if row[1] else None for row in rows}

    def get_distinct_channels(self, ann_type: str) -> list[str]:
        """Return sorted distinct non-empty biomarker values for the given annotation type."""
        rows = self._conn.execute(
            "SELECT DISTINCT biomarker FROM annotations "
            "WHERE type = ? AND biomarker != '' ORDER BY biomarker",
            (ann_type,),
        ).fetchall()
        return [r[0] for r in rows]

    def get_annotation_counts_by_slide(self) -> dict[str, dict[str, int]]:
        """Return {slide_name: {'cell_marker': N, 'region': M, 'fov': K}} for all slides."""
        rows = self._conn.execute(
            "SELECT slide_name, type, COUNT(*) FROM annotations GROUP BY slide_name, type"
        ).fetchall()
        result: dict[str, dict[str, int]] = {}
        for slide_name, ann_type, count in rows:
            if slide_name not in result:
                result[slide_name] = {"cell_marker": 0, "region": 0, "fov": 0}
            if ann_type in ("cell_marker", "region", "fov"):
                result[slide_name][ann_type] = count
        return result

    def close(self) -> None:
        self._conn.close()
