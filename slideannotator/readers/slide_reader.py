from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pyvips

from ..utils.colors import assign_channel_color
from .ome_tif import ImageReaderOmeTif
from .protocol import ChannelInfo

TILE_SIZE = 512
logger = logging.getLogger(__name__)


class OmeTifSlideReader(ImageReaderOmeTif):
    """ImageReaderOmeTif extended to implement the SlideReader protocol.

    Pre-opens each (channel, level) image with random access so tile crops
    are cheap; the rest of the metadata loading is handled by the parent.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.tile_size = TILE_SIZE
        self._tile_images: dict[tuple[int, int], pyvips.Image] = {}

        # Parent loads metadata into self.metadata
        super().__init__(str(path))

        meta = self.metadata
        self.dimensions: tuple[int, int] = (meta["width"], meta["height"])
        n_channels: int = meta["num_channels"]
        max_levels: int = max(1, meta.get("pyramid_levels", 1))

        # Pre-open images with random access for each (channel, level)
        for c in range(n_channels):
            for lv in range(max_levels):
                kwargs: dict = {"page": c, "access": "random"}
                if lv > 0:
                    kwargs["subifd"] = lv - 1
                try:
                    img = pyvips.Image.tiffload(str(path), **kwargs)
                    self._tile_images[(c, lv)] = img
                except pyvips.Error:
                    if lv == 0:
                        raise
                    break  # no more levels for this channel

        # Derive ground-truth level dimensions from the opened images
        w0 = self.dimensions[0]
        self.level_dimensions: list[tuple[int, int]] = []
        self.level_downsamples: list[float] = []
        for lv in range(max_levels):
            img = self._tile_images.get((0, lv))
            if img is None:
                break
            self.level_dimensions.append((img.width, img.height))
            self.level_downsamples.append(w0 / img.width if img.width > 0 else 1.0)
        self.level_count = len(self.level_dimensions)

        # Build ChannelInfo list
        raw_names: list[str] = meta.get("channel_names", [])
        used_colors: set[tuple[int, int, int]] = set()
        self.channels: list[ChannelInfo] = []
        for i in range(n_channels):
            label = (raw_names[i].strip() if i < len(raw_names) else "") or f"Ch{i}"
            color = assign_channel_color(label, used_colors)
            used_colors.add(color)
            self.channels.append(ChannelInfo(index=i, name=label, color=color))

        sample = self._tile_images.get((0, 0))
        _bit_map = {"uchar": 8, "ushort": 16, "uint": 32, "float": 32, "double": 64}
        self.metadata["bit_depth"] = _bit_map.get(sample.format if sample else "ushort", 16)

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

    # ------------------------------------------------------------------
    def read_tile(self, level: int, tile_x: int, tile_y: int) -> np.ndarray:
        """Return (C, tile_size, tile_size) uint16 array for the requested tile."""
        lw, lh = self.level_dimensions[level]
        ts = self.tile_size
        lx = tile_x * ts
        ly = tile_y * ts
        w = min(ts, lw - lx)
        h = min(ts, lh - ly)

        if w <= 0 or h <= 0:
            return np.zeros((len(self.channels), ts, ts), dtype=np.uint16)

        arrays: list[np.ndarray] = []
        for i in range(len(self.channels)):
            img = self._tile_images.get((i, level))
            if img is None:
                arrays.append(np.zeros((ts, ts), dtype=np.uint16))
                continue

            region = img.extract_area(lx, ly, w, h)
            raw = np.ndarray(
                shape=(region.height, region.width, region.bands),
                dtype=self._vips_dtype(region.format),
                buffer=region.write_to_memory(),
            ).copy()
            ch_arr = raw[:, :, 0] if raw.ndim == 3 else raw

            if w < ts or h < ts:
                padded = np.zeros((ts, ts), dtype=ch_arr.dtype)
                padded[:h, :w] = ch_arr
                ch_arr = padded

            arrays.append(ch_arr.astype(np.uint16) if ch_arr.dtype != np.uint16 else ch_arr)

        return np.stack(arrays)

    def read_channel_level(self, channel: int, level: int) -> np.ndarray:
        """Return the full (H, W) uint16 array for a channel at a pyramid level."""
        lw, lh = self.level_dimensions[level]
        img = self._tile_images.get((channel, level))
        if img is None:
            return np.zeros((lh, lw), dtype=np.uint16)
        buf = img.write_to_memory()
        dtype = self._vips_dtype(img.format)
        raw = np.frombuffer(buf, dtype=dtype)
        raw = (
            raw.reshape(lh, lw, img.bands)[:, :, 0]
            if img.bands > 1
            else raw.reshape(lh, lw)
        )
        return raw.astype(np.uint16) if raw.dtype != np.uint16 else raw.copy()

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
        lw, lh = self.level_dimensions[level]
        x = max(0, x)
        y = max(0, y)
        actual_w = min(w, lw - x)
        actual_h = min(h, lh - y)

        if actual_w <= 0 or actual_h <= 0:
            return np.zeros((len(self.channels), h, w), dtype=np.uint16)

        arrays: list[np.ndarray] = []
        for i in range(len(self.channels)):
            img = self._tile_images.get((i, level))
            if img is None:
                arrays.append(np.zeros((h, w), dtype=np.uint16))
                continue
            region = img.extract_area(x, y, actual_w, actual_h)
            raw = np.ndarray(
                shape=(region.height, region.width, region.bands),
                dtype=self._vips_dtype(region.format),
                buffer=region.write_to_memory(),
            ).copy()
            ch_arr = raw[:, :, 0] if raw.ndim == 3 else raw
            if actual_w < w or actual_h < h:
                padded = np.zeros((h, w), dtype=np.uint16)
                padded[:actual_h, :actual_w] = ch_arr
                ch_arr = padded
            arrays.append(ch_arr.astype(np.uint16) if ch_arr.dtype != np.uint16 else ch_arr)

        return np.stack(arrays)

    def close(self) -> None:
        self._tile_images.clear()

    @staticmethod
    def _vips_dtype(fmt: str) -> type:
        mapping = {
            "uchar": np.uint8, "char": np.int8,
            "ushort": np.uint16, "short": np.int16,
            "uint": np.uint32, "int": np.int32,
            "float": np.float32, "double": np.float64,
        }
        return mapping.get(fmt, np.uint8)
