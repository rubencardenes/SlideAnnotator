from pathlib import Path

from .ims_slide_reader import ImsSlideReader
from .protocol import ChannelInfo as ChannelInfo
from .protocol import SlideReader
from .slide_reader import OmeTifSlideReader

_SUPPORTED = {".tif", ".tiff", ".svs", ".ndpi", ".scn", ".qptiff", ".ims"}


def open_slide(path: Path) -> SlideReader:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in _SUPPORTED:
        raise ValueError(f"Unsupported file type: {path.suffix!r}")
    if suffix == ".ims":
        return ImsSlideReader(path)
    return OmeTifSlideReader(path)
