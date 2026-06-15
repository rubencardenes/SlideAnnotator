from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
)

from ..settings import get_settings


def _query_db(db_path: Path) -> dict[str, dict]:
    """Return per-type counts from the annotations DB. Returns empty dicts if DB missing."""
    result: dict[str, dict] = {
        "cell_marker": {"count": 0, "slides": 0, "biomarkers": 0, "biomarker_names": []},
        "region": {"count": 0, "slides": 0},
        "fov": {"count": 0, "slides": 0},
    }
    if not db_path.exists():
        return result

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT type, COUNT(*) AS n, COUNT(DISTINCT slide_name) AS s "
            "FROM annotations GROUP BY type"
        ).fetchall()
        for ann_type, n, s in rows:
            if ann_type in result:
                result[ann_type]["count"] = n
                result[ann_type]["slides"] = s

        marker_bio = conn.execute(
            "SELECT biomarker FROM annotations WHERE type = 'cell_marker' "
            "AND biomarker != '' GROUP BY biomarker ORDER BY biomarker"
        ).fetchall()
        result["cell_marker"]["biomarkers"] = len(marker_bio)
        result["cell_marker"]["biomarker_names"] = [r[0] for r in marker_bio]
    finally:
        conn.close()
    return result


def _make_section(title: str, rows: list[tuple[str, str, str]]) -> QGroupBox:
    box = QGroupBox(title)
    box.setStyleSheet(
        "QGroupBox {"
        "  color: #ccc; font-size: 13px; font-weight: bold;"
        "  border: 1px solid #3a3a3a; border-radius: 5px;"
        "  margin-top: 10px; padding: 10px 8px 8px 8px;"
        "}"
        "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
    )
    grid = QGridLayout(box)
    grid.setColumnStretch(0, 1)
    grid.setHorizontalSpacing(16)
    grid.setVerticalSpacing(4)

    grid_row = 0
    for label, value, subtext in rows:
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #aaa; font-size: 12px; font-weight: normal;")

        val = QLabel(value)
        val.setStyleSheet("color: #e8e8e8; font-size: 12px; font-weight: bold;")
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        grid.addWidget(lbl, grid_row, 0)
        grid.addWidget(val, grid_row, 1)
        grid_row += 1

        if subtext:
            sub = QLabel(subtext)
            sub.setStyleSheet("color: #666; font-size: 10px; font-weight: normal;")
            sub.setWordWrap(True)
            grid.addWidget(sub, grid_row, 0, 1, 2)
            grid_row += 1

    return box


class SummaryDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Annotation Summary")
        self.setMinimumWidth(380)
        self.setStyleSheet(
            "QDialog { background: #1e1e1e; }"
            "QDialogButtonBox QPushButton {"
            "  background: #2e2e2e; color: #ccc;"
            "  border: 1px solid #444; border-radius: 4px; padding: 4px 16px;"
            "}"
            "QDialogButtonBox QPushButton:hover { background: #3a3a3a; }"
        )

        db_path = get_settings().db_path.expanduser().resolve()
        stats = _query_db(db_path)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 10, 14, 14)

        db_lbl = QLabel(str(db_path))
        db_lbl.setStyleSheet("color: #555; font-size: 10px;")
        db_lbl.setWordWrap(True)
        layout.addWidget(db_lbl)

        # -- FOVs --
        fov = stats["fov"]
        layout.addWidget(
            _make_section(
                "FOVs",
                [
                    ("FOVs", f"{fov['count']:,}", ""),
                    ("Slides", str(fov["slides"]), ""),
                ],
            )
        )

        # -- Marker Annotations --
        mk = stats["cell_marker"]
        names = mk["biomarker_names"]
        channels_str = ""
        if names:
            joined = ", ".join(names)
            channels_str = joined if len(joined) <= 60 else joined[:57] + "…"
        layout.addWidget(
            _make_section(
                "Marker Annotations",
                [
                    ("Cell marker annotations", f"{mk['count']:,}", ""),
                    ("Biomarkers", str(mk["biomarkers"]), channels_str),
                    ("Slides", str(mk["slides"]), ""),
                ],
            )
        )

        # -- Region Annotations --
        rg = stats["region"]
        layout.addWidget(
            _make_section(
                "Region Annotations",
                [
                    ("Region annotations", f"{rg['count']:,}", ""),
                    ("Slides", str(rg["slides"]), ""),
                ],
            )
        )

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
