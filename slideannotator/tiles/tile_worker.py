from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, QRunnable, Signal
from PySide6.QtGui import QImage

from ..compositing.compositor import ChannelSettings, composite_channels
from ..readers.protocol import SlideReader
from .tile_cache import LRUCache, TileKey


class _Signals(QObject):
    tile_ready = Signal(object, object, int)   # TileKey, QImage, generation
    tile_failed = Signal(object, str, int)     # TileKey, error, generation


class TileWorker(QRunnable):
    def __init__(
        self,
        key: TileKey,
        reader: SlideReader,
        raw_cache: LRUCache,
        channel_settings: list[ChannelSettings],
        generation: int,
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._key = key
        self._reader = reader
        self._raw_cache = raw_cache
        self._settings = channel_settings
        self._generation = generation
        self.signals = _Signals()

    def run(self) -> None:
        key = self._key
        try:
            raw = self._raw_cache.get(key)
            if raw is None:
                raw = self._reader.read_tile(key.level, key.tile_x, key.tile_y)
                self._raw_cache.put(key, raw)

            rgba = composite_channels(raw, self._settings)
            rgba = np.ascontiguousarray(rgba)
            h, w = rgba.shape[:2]
            qimage = QImage(
                rgba.data, w, h, w * 4, QImage.Format.Format_RGBA8888
            ).copy()

            self.signals.tile_ready.emit(key, qimage, self._generation)
        except Exception as exc:
            self.signals.tile_failed.emit(key, str(exc), self._generation)
