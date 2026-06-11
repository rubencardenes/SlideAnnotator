from pathlib import Path
from .protocol import SlideReader, ChannelInfo
from .slide_reader import OmeTifSlideReader
from .ims_slide_reader import ImsSlideReader

_SUPPORTED = {".tif", ".tiff", ".svs", ".ndpi", ".scn", ".qptiff", ".ims"}


def open_slide(path: Path) -> SlideReader:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in _SUPPORTED:
        raise ValueError(f"Unsupported file type: {path.suffix!r}")
    if suffix == ".ims":
        return ImsSlideReader(path)
    return OmeTifSlideReader(path)
