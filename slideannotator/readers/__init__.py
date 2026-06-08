from pathlib import Path
from .protocol import SlideReader, ChannelInfo
from .slide_reader import OmeTifSlideReader

_SUPPORTED = {".tif", ".tiff", ".svs", ".ndpi", ".scn", ".qptiff"}


def open_slide(path: Path) -> SlideReader:
    path = Path(path)
    if path.suffix.lower() not in _SUPPORTED:
        raise ValueError(f"Unsupported file type: {path.suffix!r}")
    return OmeTifSlideReader(path)
