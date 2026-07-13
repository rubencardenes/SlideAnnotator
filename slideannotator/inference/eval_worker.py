"""Background worker that evaluates the cell-detection model against annotations.

The worker is handed a list of :class:`SlideEvalJob` objects (built on the main
thread from the annotation database) and, for each FOV, runs the detector,
matches predictions to ground-truth boxes and accumulates per-marker metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ..readers import open_slide
from .CellONNXInference import CellONNXInferDFINE
from .evaluation import Box, EvaluationResult, match_boxes

_TILE_SIZE = 512


@dataclass
class FovGT:
    """A field of view plus its ground-truth boxes, grouped by marker."""

    x: int
    y: int
    w: int
    h: int
    boxes_by_marker: dict[str, list[Box]] = field(default_factory=dict)


@dataclass
class SlideEvalJob:
    """Everything the worker needs to evaluate a single slide."""

    slide_name: str
    slide_path: Path
    fovs: list[FovGT] = field(default_factory=list)


def _find_dapi_channel(reader) -> int | None:
    for i, ch in enumerate(reader.channels):
        n = ch.name.lower()
        if "dapi" in n or "hoechst" in n:
            return i
    return None


class _Signals(QObject):
    progress = Signal(int, int)  # (fovs_done, fovs_total)
    finished = Signal(object)  # EvaluationResult
    error = Signal(str)


class EvaluationWorker(QRunnable):
    """Runs object-detection evaluation over a set of annotated slides."""

    def __init__(
        self,
        model: CellONNXInferDFINE,
        jobs: list[SlideEvalJob],
        iou_threshold: float,
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._model = model
        self._jobs = jobs
        self._iou_threshold = iou_threshold
        self.signals = _Signals()

    # ------------------------------------------------------------------
    def _build_tile(
        self, raw: np.ndarray, ty: int, tx: int, red: int, blue: int | None
    ) -> np.ndarray:
        """Return a (512, 512, 3) uint16 tile: red=marker, green=0, blue=DAPI."""
        h = min(_TILE_SIZE, raw.shape[1] - ty)
        w = min(_TILE_SIZE, raw.shape[2] - tx)
        tile = np.zeros((_TILE_SIZE, _TILE_SIZE, 3), dtype=np.uint16)
        tile[:h, :w, 0] = raw[red, ty : ty + h, tx : tx + w].astype(np.uint16)
        if blue is not None:
            tile[:h, :w, 2] = raw[blue, ty : ty + h, tx : tx + w].astype(np.uint16)
        return tile

    def _predict_fov(
        self, raw: np.ndarray, ox: int, oy: int, fw: int, fh: int, red: int, blue: int | None
    ) -> list[Box]:
        """Run the detector over an FOV (tiled) and return scene-space boxes."""
        boxes: list[Box] = []
        for ty in range(0, fh, _TILE_SIZE):
            for tx in range(0, fw, _TILE_SIZE):
                tile = self._build_tile(raw, ty, tx, red, blue)
                for row in self._model.predict(tile):  # (N, 5): x1,y1,x2,y2,score
                    boxes.append(
                        (
                            float(row[0]) + ox + tx,
                            float(row[1]) + oy + ty,
                            float(row[2]) + ox + tx,
                            float(row[3]) + oy + ty,
                        )
                    )
        return boxes

    @Slot()
    def run(self) -> None:
        try:
            result = EvaluationResult(
                task="detection",
                iou_threshold=self._iou_threshold,
                n_slides=len(self._jobs),
            )
            total = sum(len(job.fovs) for job in self._jobs)
            done = 0

            for job in self._jobs:
                try:
                    reader = open_slide(job.slide_path)
                except Exception:
                    result.skipped_slides.append(job.slide_name)
                    done += len(job.fovs)
                    self.signals.progress.emit(done, total)
                    continue

                result.images.append(job.slide_name)

                try:
                    ch_index = {ch.name: i for i, ch in enumerate(reader.channels)}
                    dapi_idx = _find_dapi_channel(reader)

                    for fov in job.fovs:
                        raw = reader.read_region(0, fov.x, fov.y, fov.w, fov.h)  # (C, H, W)
                        for marker, gt_boxes in fov.boxes_by_marker.items():
                            red = ch_index.get(marker)
                            if red is None:
                                continue
                            pred_boxes = self._predict_fov(
                                raw, fov.x, fov.y, fov.w, fov.h, red, dapi_idx
                            )
                            tp, fp, fn = match_boxes(gt_boxes, pred_boxes, self._iou_threshold)
                            result.detection_result_for(marker).add(tp, fp, fn)
                        done += 1
                        self.signals.progress.emit(done, total)
                finally:
                    reader.close()

            self.signals.finished.emit(result)
        except Exception as exc:  # pragma: no cover - defensive
            self.signals.error.emit(str(exc))
