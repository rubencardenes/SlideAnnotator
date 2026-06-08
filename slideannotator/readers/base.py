import abc
import re
import xml.etree.ElementTree as ET
from typing import Any

import numpy as np

_MICRON_SCALE = {"m": 1e6, "cm": 1e4, "mm": 1e3, "µm": 1.0, "um": 1.0, "nm": 1e-3}


def _to_microns(value: float, unit: str) -> float:
    return value * _MICRON_SCALE.get(unit, 1.0)


def _best_pyramid_level(factor: int, num_levels: int) -> tuple[int, int]:
    """Return (level, level_factor) where level_factor is the largest power-of-2 ≤ factor."""
    best_level, best_factor = 0, 1
    for k in range(num_levels):
        level_factor = 1 << k  # 2^k
        if level_factor <= factor:
            best_level, best_factor = k, level_factor
    return best_level, best_factor


def _parse_ome_xml(xml_str: str, metadata: dict) -> None:
    """Parse OME-XML string and populate metadata dict in-place."""
    root = ET.fromstring(xml_str)
    ns_match = re.match(r"\{(.+)\}", root.tag)
    ns = f"{{{ns_match.group(1)}}}" if ns_match else ""

    pixels = root.find(f".//{ns}Pixels")
    if pixels is not None:
        metadata["num_channels"] = int(pixels.get("SizeC", 0))

        phys_x = pixels.get("PhysicalSizeX")
        phys_y = pixels.get("PhysicalSizeY")
        if phys_x:
            metadata["pixel_size_x"] = _to_microns(
                float(phys_x), pixels.get("PhysicalSizeXUnit", "µm")
            )
        if phys_y:
            metadata["pixel_size_y"] = _to_microns(
                float(phys_y), pixels.get("PhysicalSizeYUnit", "µm")
            )

        metadata["channel_names"] = [ch.get("Name", "") for ch in pixels.findall(f"{ns}Channel")]

    objective = root.find(f".//{ns}Objective")
    if objective is not None:
        mag = objective.get("NominalMagnification")
        if mag:
            metadata["magnification"] = float(mag)


class ImageReader(abc.ABC):
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.metadata: dict[str, Any] = {
            "width": 0,
            "height": 0,
            "num_channels": 0,
            "num_scenes": 0,
            "pixel_size_x": 0.0,
            "pixel_size_y": 0.0,
            "pixel_size_unit": "µm",
            "magnification": 0.0,
            "channel_names": [],
            "marker_names": [],
            "exposure_times": [],
            "pyramid_levels": 0,
            "pyramid_info": [],
        }
        self._load_metadata()

    def __repr__(self) -> str:
        lines = [f"{self.__class__.__name__}("]
        lines.append(f"  filepath       = {self.filepath!r}")
        for k, v in self.metadata.items():
            if k == "pyramid_info":
                lines.append(f"  {'pyramid_info':<16} =")
                for entry in v:
                    lines.append(
                        f"    level {entry['level']}: factor={entry['factor']:<4} "
                        f"{entry['width']}x{entry['height']}"
                    )
            else:
                lines.append(f"  {k:<16} = {v!r}")
        lines.append(")")
        return "\n".join(lines)

    @abc.abstractmethod
    def _load_metadata(self):
        pass

    @abc.abstractmethod
    def get_region(self, x: int, y: int, w: int, h: int, channel: int) -> np.ndarray:
        """Read a region at full resolution for a single channel."""
        pass

    @abc.abstractmethod
    def get_downsampled(self, factor: int, channel: int) -> np.ndarray:
        """Read the full image at a given downsampling factor for a single channel."""
        pass
