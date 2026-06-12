from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

_SEARCH_PATHS = [
    Path(__file__).parent.parent / "settings.yaml",          # project root (dev)
    Path.home() / ".config" / "slideannotator" / "settings.yaml",  # user config
]

_DEFAULTS = {
    "annotations_dir": "~/data/annotations",
}


@dataclass
class Settings:
    annotations_dir: Path = field(default_factory=lambda: Path.home() / "data" / "annotations")
    stardist_model: Path | None = field(default=None)
    cell_det_model: Path | None = field(default=None)
    db_path: Path = field(default_factory=lambda: Path("annotations.db"))
    data_dir: Path | None = field(default=None)

    @staticmethod
    def from_dict(data: dict) -> Settings:
        s = Settings()
        if "annotations_dir" in data:
            s.annotations_dir = Path(data["annotations_dir"]).expanduser()
        if "stardist_model" in data:
            s.stardist_model = Path(data["stardist_model"]).expanduser()
        if "cell_det_model" in data:
            s.cell_det_model = Path(data["cell_det_model"]).expanduser()
        if "db_path" in data:
            s.db_path = Path(data["db_path"]).expanduser()
        if "data_dir" in data:
            s.data_dir = Path(data["data_dir"]).expanduser()
        return s


_cached: Settings | None = None


def get_settings() -> Settings:
    global _cached
    if _cached is None:
        _cached = _load()
    return _cached


def _load() -> Settings:
    for path in _SEARCH_PATHS:
        if path.exists():
            try:
                raw = yaml.safe_load(path.read_text()) or {}
                return Settings.from_dict(raw)
            except Exception:
                pass
    return Settings.from_dict(_DEFAULTS)
