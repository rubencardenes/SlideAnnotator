from __future__ import annotations

from pathlib import Path

import numpy as np
import pyvips
from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ..annotations.models import FOVAnnotation
from .CellONNXInference import CellONNXInferDFINE

_TILE_SIZE = 512
# TODO: remove debug — temp dir for saving inference tiles
_DEBUG_TILE_DIR = Path(__file__).parents[2] / "tmp" / "cell_det_tiles"
_DEBUG_TILE_DIR.mkdir(parents=True, exist_ok=True)


class _Signals(QObject):
    finished = Signal(list)   # list[tuple[float, float, float, float]]  — scene-space (xmin,ymin,xmax,ymax)
    error = Signal(str)


class CellDetWorker(QRunnable):
    """Runs DFINE cell detection on FOV tiles in a background thread.

    The FOV is split into non-overlapping 512×512 tiles (zero-padded at edges).
    Detected box centres are converted to scene coordinates and emitted via
    ``signals.finished``.
    """

    def __init__(
        self,
        model: CellONNXInferDFINE,
        fovs: list[FOVAnnotation],
        reader,
        channel_r: int | None,
        channel_g: int | None,
        channel_b: int | None,
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._model = model
        self._fovs = fovs
        self._reader = reader
        self._channel_r = channel_r
        self._channel_g = channel_g
        self._channel_b = channel_b
        self.signals = _Signals()

    def _build_tile(self, raw: np.ndarray, ty: int, tx: int) -> np.ndarray:
        """Return a (512, 512, 3) uint16 tile from a (C, H, W) raw array."""
        h = min(_TILE_SIZE, raw.shape[1] - ty)
        w = min(_TILE_SIZE, raw.shape[2] - tx)
        tile = np.zeros((_TILE_SIZE, _TILE_SIZE, 3), dtype=np.uint16)

        def _ch(idx: int | None) -> np.ndarray:
            if idx is None:
                return np.zeros((h, w), dtype=np.uint16)
            return raw[idx, ty : ty + h, tx : tx + w].astype(np.uint16)

        tile[:h, :w, 0] = _ch(self._channel_r)
        tile[:h, :w, 1] = _ch(self._channel_g)
        tile[:h, :w, 2] = _ch(self._channel_b)
        return tile

    @Slot()
    def run(self) -> None:
        try:
            all_boxes: list[tuple[float, float, float, float]] = []
            for fov in self._fovs:
                ox, oy = int(fov.x), int(fov.y)
                fw, fh = int(fov.w), int(fov.h)
                raw = self._reader.read_region(0, ox, oy, fw, fh)  # (C, H, W)

                for ty in range(0, fh, _TILE_SIZE):
                    for tx in range(0, fw, _TILE_SIZE):
                        tile = self._build_tile(raw, ty, tx)
                        boxes = self._model.predict(tile)  # (N, 5) xmin,ymin,xmax,ymax,score
                        for row in boxes:
                            xmin = float(row[0]) + ox + tx
                            ymin = float(row[1]) + oy + ty
                            xmax = float(row[2]) + ox + tx
                            ymax = float(row[3]) + oy + ty
                            all_boxes.append((xmin, ymin, xmax, ymax))

            self.signals.finished.emit(all_boxes)
        except Exception as exc:
            self.signals.error.emit(str(exc))
