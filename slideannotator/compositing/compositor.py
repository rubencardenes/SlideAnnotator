from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ChannelSettings:
    visible: bool = True
    color: tuple[int, int, int] = (255, 255, 255)
    min_val: float = 0.0
    max_val: float = 65535.0

    def copy(self) -> ChannelSettings:
        return ChannelSettings(
            visible=self.visible,
            color=self.color,
            min_val=self.min_val,
            max_val=self.max_val,
        )


def composite_channels(
    raw: np.ndarray,
    settings: list[ChannelSettings],
) -> np.ndarray:
    """
    Composite multiple fluorescence channels into an RGBA image.

    raw: (C, H, W) uint16 — one slice per channel
    returns: (H, W, 4) uint8 RGBA
    """
    if raw.ndim == 3 and raw.shape[2] == 4:
        # Already RGBA (RGB slide) — pass through
        return raw.astype(np.uint8)

    c_count, h, w = raw.shape
    result = np.zeros((h, w, 3), dtype=np.float32)

    for i, s in enumerate(settings[:c_count]):
        if not s.visible:
            continue
        ch = raw[i].astype(np.float32)
        span = max(s.max_val - s.min_val, 1.0)
        ch = np.clip((ch - s.min_val) / span, 0.0, 1.0)
        color = np.array(s.color, dtype=np.float32) / 255.0
        result += ch[:, :, np.newaxis] * color

    result = np.clip(result, 0.0, 1.0)
    rgba = np.empty((h, w, 4), dtype=np.uint8)
    rgba[:, :, :3] = (result * 255.0).astype(np.uint8)
    rgba[:, :, 3] = 255
    return rgba
