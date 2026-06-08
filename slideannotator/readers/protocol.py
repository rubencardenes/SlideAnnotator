from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np


@dataclass
class ChannelInfo:
    index: int
    name: str
    color: tuple[int, int, int]
    is_rgb: bool = False


class SlideReader(Protocol):
    path: Path
    dimensions: tuple[int, int]
    level_count: int
    level_dimensions: list[tuple[int, int]]
    level_downsamples: list[float]
    channels: list[ChannelInfo]
    tile_size: int

    def read_tile(self, level: int, tile_x: int, tile_y: int) -> np.ndarray:
        """Return (C, tile_size, tile_size) uint16 array, or (tile_size, tile_size, 4) uint8 for RGB."""
        ...

    def get_best_level(self, downsample: float) -> int:
        """Return highest pyramid level whose downsample factor <= requested downsample."""
        ...

    def close(self) -> None:
        ...
