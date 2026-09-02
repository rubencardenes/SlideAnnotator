from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyvips

from ..utils.colors import assign_channel_color
from .protocol import ChannelInfo

TILE_SIZE = 512
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _QptiffPage:
    page: int
    width: int
    height: int
    image_type: str
    channel_name: str
    color: tuple[int, int, int] | None
    tiled: bool


def _xml_text(root: ET.Element, name: str) -> str:
    """Return an element's text while ignoring optional XML namespaces."""
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == name:
            return (element.text or "").strip()
    return ""


def _parse_color(value: str) -> tuple[int, int, int] | None:
    try:
        values = tuple(int(part.strip()) for part in value.split(","))
    except ValueError:
        return None
    if len(values) != 3 or any(component < 0 or component > 255 for component in values):
        return None
    return values


class QptiffSlideReader:
    """Reader for PerkinElmer/Akoya QPTIFF whole-slide images.

    QPTIFF stores channels and pyramid levels as ordinary TIFF pages rather
    than OME-TIFF SubIFDs. Page XML is inspected to build an explicit mapping,
    so auxiliary thumbnail, overview, and label pages may occur anywhere.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.tile_size = TILE_SIZE
        self._tile_images: dict[tuple[int, int], pyvips.Image] = {}
        self.metadata: dict = {}

        pages = self._discover_pages()
        image_pages = [
            page
            for page in pages
            if page.image_type.lower() in {"fullresolution", "reducedresolution"}
            and page.channel_name
            and page.width > 0
            and page.height > 0
        ]
        if not image_pages:
            raise ValueError(
                "No FullResolution or ReducedResolution channel pages were found in QPTIFF"
            )

        groups: dict[tuple[int, int], list[_QptiffPage]] = {}
        for page in image_pages:
            groups.setdefault((page.width, page.height), []).append(page)

        full_resolution = [p for p in image_pages if p.image_type.lower() == "fullresolution"]
        base_group = max(
            (groups[(p.width, p.height)] for p in full_resolution),
            key=lambda group: group[0].width * group[0].height,
            default=max(groups.values(), key=lambda group: group[0].width * group[0].height),
        )
        base_group = sorted(base_group, key=lambda page: page.page)
        channel_names = list(dict.fromkeys(page.channel_name for page in base_group))
        if not channel_names:
            raise ValueError("QPTIFF full-resolution pages do not contain channel names")

        # Ignore unrelated image series: a pyramid level must contain every
        # full-resolution channel exactly once.
        level_groups: list[tuple[tuple[int, int], dict[str, _QptiffPage]]] = []
        for dimensions, group in groups.items():
            by_name: dict[str, _QptiffPage] = {}
            for page in sorted(group, key=lambda item: item.page):
                by_name.setdefault(page.channel_name, page)
            if all(name in by_name for name in channel_names):
                level_groups.append((dimensions, by_name))
        level_groups.sort(key=lambda item: item[0][0] * item[0][1], reverse=True)
        if not level_groups:
            raise ValueError("QPTIFF does not contain a complete channel level")

        self.dimensions = level_groups[0][0]
        self.level_dimensions = [dimensions for dimensions, _ in level_groups]
        self.level_downsamples = [self.dimensions[0] / width for width, _ in self.level_dimensions]
        self.level_count = len(self.level_dimensions)

        base_by_name = {page.channel_name: page for page in base_group}
        self.channels = []
        for index, name in enumerate(channel_names):
            color = base_by_name[name].color or assign_channel_color(name, index)
            self.channels.append(ChannelInfo(index=index, name=name, color=color))

        for level, (_, by_name) in enumerate(level_groups):
            for channel, name in enumerate(channel_names):
                page = by_name[name]
                if page.tiled:
                    image = pyvips.Image.tiffload(str(self.path), page=page.page, access="random")
                else:
                    # Small QPTIFF pyramid levels are often stripped. libtiff
                    # cannot serve arbitrary tile reads from those pages, so
                    # materialize them once in their natural scan order.
                    image = pyvips.Image.tiffload(
                        str(self.path), page=page.page, access="sequential"
                    ).copy_memory()
                self._tile_images[(channel, level)] = image

        sample = self._tile_images[(0, 0)]
        bit_map = {"uchar": 8, "ushort": 16, "uint": 32, "float": 32, "double": 64}
        self.metadata.update(
            {
                "width": self.dimensions[0],
                "height": self.dimensions[1],
                "num_channels": len(self.channels),
                "num_scenes": 1,
                "channel_names": channel_names,
                "pyramid_levels": self.level_count,
                "pyramid_info": [
                    {
                        "level": level,
                        "factor": self.level_downsamples[level],
                        "width": width,
                        "height": height,
                    }
                    for level, (width, height) in enumerate(self.level_dimensions)
                ],
                "bit_depth": bit_map.get(sample.format, 8),
            }
        )

        logger.info(
            "Opened QPTIFF %s: %d channels, %d pyramid levels",
            self.path.name,
            len(self.channels),
            self.level_count,
        )

    def _discover_pages(self) -> list[_QptiffPage]:
        first = pyvips.Image.tiffload(str(self.path), page=0)
        fields = first.get_fields()
        page_count = int(first.get("n-pages")) if "n-pages" in fields else 1
        pages: list[_QptiffPage] = []

        for page_number in range(page_count):
            image = pyvips.Image.tiffload(str(self.path), page=page_number)
            image_fields = image.get_fields()
            description = (
                image.get("image-description") if "image-description" in image_fields else ""
            )
            try:
                root = ET.fromstring(description)
            except (ET.ParseError, TypeError):
                logger.debug("Ignoring TIFF page %d without valid QPTIFF XML", page_number)
                continue

            root_name = root.tag.rsplit("}", 1)[-1].lower()
            if root_name != "perkinelmer-qpi-imagedescription":
                continue
            name = _xml_text(root, "Name") or _xml_text(root, "Biomarker")
            pages.append(
                _QptiffPage(
                    page=page_number,
                    width=image.width,
                    height=image.height,
                    image_type=_xml_text(root, "ImageType"),
                    channel_name=name,
                    color=_parse_color(_xml_text(root, "Color")),
                    tiled="tile-width" in image_fields and "tile-height" in image_fields,
                )
            )
        return pages

    def read_tile(self, level: int, tile_x: int, tile_y: int) -> np.ndarray:
        width, height = self.level_dimensions[level]
        x = tile_x * self.tile_size
        y = tile_y * self.tile_size
        return self.read_region(level, x, y, self.tile_size, self.tile_size)

    def read_channel_level(self, channel: int, level: int) -> np.ndarray:
        width, height = self.level_dimensions[level]
        return self._image_to_array(self._tile_images[(channel, level)], width, height)

    def compute_channel_quantiles(
        self, level: int, q_low: float = 0.001, q_high: float = 0.999
    ) -> list[tuple[float, float]]:
        results = []
        for channel in range(len(self.channels)):
            array = self.read_channel_level(channel, level)
            low = float(np.quantile(array, q_low))
            high = float(np.quantile(array, q_high))
            results.append((max(low, 0.0), max(high, low + 1.0)))
        return results

    def get_best_level(self, downsample: float) -> int:
        best = 0
        for level, level_downsample in enumerate(self.level_downsamples):
            if level_downsample <= downsample + 1e-6:
                best = level
        return best

    def read_region(self, level: int, x: int, y: int, w: int, h: int) -> np.ndarray:
        level_width, level_height = self.level_dimensions[level]
        x = max(0, x)
        y = max(0, y)
        actual_width = min(w, level_width - x)
        actual_height = min(h, level_height - y)
        if actual_width <= 0 or actual_height <= 0:
            return np.zeros((len(self.channels), h, w), dtype=np.uint16)

        arrays = []
        for channel in range(len(self.channels)):
            region = self._tile_images[(channel, level)].extract_area(
                x, y, actual_width, actual_height
            )
            array = self._image_to_array(region, actual_width, actual_height)
            if actual_width < w or actual_height < h:
                padded = np.zeros((h, w), dtype=array.dtype)
                padded[:actual_height, :actual_width] = array
                array = padded
            arrays.append(array.astype(np.uint16) if array.dtype != np.uint16 else array)
        return np.stack(arrays)

    def close(self) -> None:
        self._tile_images.clear()

    @staticmethod
    def _image_to_array(image: pyvips.Image, width: int, height: int) -> np.ndarray:
        dtype_map = {
            "uchar": np.uint8,
            "char": np.int8,
            "ushort": np.uint16,
            "short": np.int16,
            "uint": np.uint32,
            "int": np.int32,
            "float": np.float32,
            "double": np.float64,
        }
        array = np.frombuffer(image.write_to_memory(), dtype=dtype_map[image.format])
        if image.bands > 1:
            return array.reshape(height, width, image.bands)[:, :, 0].copy()
        return array.reshape(height, width).copy()
