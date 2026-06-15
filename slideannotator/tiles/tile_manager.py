from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, QRectF, QThreadPool, Signal
from PySide6.QtGui import QImage

from ..compositing.compositor import ChannelSettings
from ..readers.protocol import SlideReader
from .tile_cache import LRUCache, TileKey
from .tile_worker import TileWorker


class TileManager(QObject):
    tile_ready = Signal(object, object)  # TileKey, QImage

    def __init__(
        self,
        reader: SlideReader,
        raw_cache: LRUCache,
        composited_cache: LRUCache,
        thread_pool: QThreadPool,
    ) -> None:
        super().__init__()
        self._reader = reader
        self._raw_cache = raw_cache
        self._composited_cache = composited_cache
        self._thread_pool = thread_pool
        self._in_flight: set[TileKey] = set()
        self._generation = 0

    # ------------------------------------------------------------------
    def request_tiles(
        self,
        viewport_rect: QRectF,
        zoom: float,
        channel_settings: list[ChannelSettings],
    ) -> None:
        gen = self._generation
        level = self._reader.get_best_level(max(1.0 / max(zoom, 1e-6), 1.0))
        ds = self._reader.level_downsamples[level]
        ts = self._reader.tile_size
        lw, lh = self._reader.level_dimensions[level]

        # Convert viewport (level-0 coords) to level-N tile grid
        vl_x = viewport_rect.left() / ds
        vl_y = viewport_rect.top() / ds
        vl_r = viewport_rect.right() / ds
        vl_b = viewport_rect.bottom() / ds

        tx_min = max(0, int(vl_x / ts))
        ty_min = max(0, int(vl_y / ts))
        tx_max = min((lw + ts - 1) // ts, int(vl_r / ts) + 1)
        ty_max = min((lh + ts - 1) // ts, int(vl_b / ts) + 1)

        settings_copy = [s.copy() for s in channel_settings]

        for ty in range(ty_min, ty_max + 1):
            for tx in range(tx_min, tx_max + 1):
                key = TileKey(str(self._reader.path), level, tx, ty)

                cached = self._composited_cache.get(key)
                if cached is not None:
                    self.tile_ready.emit(key, cached)
                    continue

                if key not in self._in_flight:
                    self._in_flight.add(key)
                    worker = TileWorker(key, self._reader, self._raw_cache, settings_copy, gen)
                    worker.signals.tile_ready.connect(self._on_worker_ready)
                    worker.signals.tile_failed.connect(self._on_worker_failed)
                    self._thread_pool.start(worker)

    def load_thumbnail_sync(
        self,
        channel_settings: list[ChannelSettings],
    ) -> tuple[QImage, float] | None:
        """Synchronously composite the coarsest pyramid level for immediate display.

        Returns (QImage, downsample) or None if not feasible (single-level image or
        coarsest level exceeds the size guard).
        """
        reader = self._reader
        if reader.level_count < 2:
            return None
        level = reader.level_count - 1
        lw, lh = reader.level_dimensions[level]
        if lw * lh > 2000 * 2000:
            return None

        ds = reader.level_downsamples[level]
        acc = np.zeros((lh, lw, 3), dtype=np.float32)
        for i, s in enumerate(channel_settings[: len(reader.channels)]):
            if not s.visible:
                continue
            raw = reader.read_channel_level(i, level).astype(np.float32)
            span = max(s.max_val - s.min_val, 1.0)
            np.clip((raw - s.min_val) / span, 0.0, 1.0, out=raw)
            color = np.array(s.color, dtype=np.float32) / 255.0
            acc += raw[:, :, np.newaxis] * color

        np.clip(acc, 0.0, 1.0, out=acc)
        rgba = np.empty((lh, lw, 4), dtype=np.uint8)
        rgba[:, :, :3] = (acc * 255.0).astype(np.uint8)
        rgba[:, :, 3] = 255
        rgba = np.ascontiguousarray(rgba)
        qimage = QImage(rgba.data, lw, lh, lw * 4, QImage.Format.Format_RGBA8888).copy()
        return qimage, ds

    def invalidate_composited_cache(self) -> None:
        self._composited_cache.clear()
        self._in_flight.clear()
        self._generation += 1

    # ------------------------------------------------------------------
    def _on_worker_ready(self, key: TileKey, qimage, generation: int) -> None:
        self._in_flight.discard(key)
        if generation != self._generation:
            return
        self._composited_cache.put(key, qimage)
        self.tile_ready.emit(key, qimage)

    def _on_worker_failed(self, key: TileKey, error: str, generation: int) -> None:
        self._in_flight.discard(key)
