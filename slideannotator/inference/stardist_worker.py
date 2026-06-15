from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ..annotations.models import FOVAnnotation
from .stardist import StarDistONNX


class _Signals(QObject):
    finished = Signal(list)  # list[list[tuple[float, float]]]
    error = Signal(str)


class StarDistWorker(QRunnable):
    """Runs StarDist inference on a list of FOVs in a background thread.

    Emits ``signals.finished`` with all polygon vertices offset to scene
    coordinates, or ``signals.error`` on failure.
    """

    def __init__(
        self,
        model: StarDistONNX,
        fovs: list[FOVAnnotation],
        reader,
        channel_idx: int,
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._model = model
        self._fovs = fovs
        self._reader = reader
        self._channel_idx = channel_idx
        self.signals = _Signals()

    @Slot()
    def run(self) -> None:
        try:
            all_polygons: list[list[tuple[float, float]]] = []
            for fov in self._fovs:
                x, y = int(fov.x), int(fov.y)
                w, h = int(fov.w), int(fov.h)
                raw = self._reader.read_region(0, x, y, w, h)  # (C, H, W)
                channel_img = raw[self._channel_idx]  # (H, W)
                polys = self._model.predict_polygons(channel_img)
                for poly in polys:
                    all_polygons.append([(px + x, py + y) for px, py in poly])
            self.signals.finished.emit(all_polygons)
        except Exception as exc:
            self.signals.error.emit(str(exc))
