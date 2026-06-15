from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from ..utils.colors import assign_channel_color
from .ims import ImageReaderIms
from .protocol import ChannelInfo

TILE_SIZE = 512
logger = logging.getLogger(__name__)


class ImsSlideReader(ImageReaderIms):
    """ImageReaderIms extended to implement the SlideReader protocol."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.tile_size = TILE_SIZE

        super().__init__(str(path))

        meta = self.metadata
        self.dimensions: tuple[int, int] = (meta["width"], meta["height"])

        pyr_info = meta["pyramid_info"]
        self.level_dimensions: list[tuple[int, int]] = [
            (entry["width"], entry["height"]) for entry in pyr_info
        ]
        self.level_downsamples: list[float] = [float(entry["factor"]) for entry in pyr_info]
        self.level_count = len(self.level_dimensions)

        raw_names: list[str] = meta.get("channel_names", [])
        n_channels: int = meta["num_channels"]
        used_colors: set[tuple[int, int, int]] = set()
        self.channels: list[ChannelInfo] = []
        for i in range(n_channels):
            label = (raw_names[i].strip() if i < len(raw_names) else "") or f"Ch{i}"
            color = assign_channel_color(label, used_colors)
            used_colors.add(color)
            self.channels.append(ChannelInfo(index=i, name=label, color=color))

        if self._res_keys:
            try:
                ds0 = self._f["DataSet"][self._res_keys[0]]["TimePoint 0"]["Channel 0"]["Data"]
                self.metadata["bit_depth"] = int(ds0.dtype.itemsize * 8)
            except Exception:
                self.metadata["bit_depth"] = 16
        else:
            self.metadata["bit_depth"] = 16

        logger.info("Opened: %s", path.name)
        logger.info(
            "  Channels: %d  (%s)",
            len(self.channels),
            ", ".join(c.name for c in self.channels),
        )
        logger.info("  Pyramid levels: %d", self.level_count)
        for lv, (lw, lh) in enumerate(self.level_dimensions):
            ds = self.level_downsamples[lv]
            logger.info("    Level %d: %d × %d  (downsample ×%.2f)", lv, lw, lh, ds)

    def _read_level_region(
        self, level: int, channel: int, x: int, y: int, w: int, h: int
    ) -> np.ndarray:
        lw, lh = self.level_dimensions[level]
        x = max(0, x)
        y = max(0, y)
        actual_w = min(w, lw - x)
        actual_h = min(h, lh - y)

        if actual_w <= 0 or actual_h <= 0:
            return np.zeros((h, w), dtype=np.uint16)

        arr = self._level_data(level, channel)[0, y : y + actual_h, x : x + actual_w]
        arr = arr.astype(np.uint16)

        if actual_w < w or actual_h < h:
            padded = np.zeros((h, w), dtype=np.uint16)
            padded[:actual_h, :actual_w] = arr
            return padded
        return arr

    def read_tile(self, level: int, tile_x: int, tile_y: int) -> np.ndarray:
        """Return (C, tile_size, tile_size) uint16 array for the requested tile."""
        ts = self.tile_size
        lx = tile_x * ts
        ly = tile_y * ts
        lw, lh = self.level_dimensions[level]
        w = min(ts, lw - lx)
        h = min(ts, lh - ly)

        if w <= 0 or h <= 0:
            return np.zeros((len(self.channels), ts, ts), dtype=np.uint16)

        arrays = [
            self._read_level_region(level, i, lx, ly, ts, ts) for i in range(len(self.channels))
        ]
        return np.stack(arrays)

    def read_channel_level(self, channel: int, level: int) -> np.ndarray:
        """Return the full (H, W) uint16 array for a channel at a pyramid level."""
        arr = self._level_data(level, channel)[0]
        return arr.astype(np.uint16)

    def compute_channel_quantiles(
        self, level: int, q_low: float = 0.001, q_high: float = 0.999
    ) -> list[tuple[float, float]]:
        results: list[tuple[float, float]] = []
        for c in range(len(self.channels)):
            arr = self.read_channel_level(c, level)
            lo = float(np.quantile(arr, q_low))
            hi = float(np.quantile(arr, q_high))
            results.append((max(lo, 0.0), max(hi, lo + 1.0)))
        return results

    def get_best_level(self, downsample: float) -> int:
        best = 0
        for i, ds in enumerate(self.level_downsamples):
            if ds <= downsample + 1e-6:
                best = i
        return best

    def read_region(self, level: int, x: int, y: int, w: int, h: int) -> np.ndarray:
        """Return (C, h, w) uint16 for the requested region at the given level."""
        arrays = [self._read_level_region(level, i, x, y, w, h) for i in range(len(self.channels))]
        return np.stack(arrays)

    def close(self) -> None:
        super().close()
