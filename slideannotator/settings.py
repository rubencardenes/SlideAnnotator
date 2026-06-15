from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

_SEARCH_PATHS = [
    Path(__file__).parent.parent / "settings.yaml",  # project root (dev)
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
    fov_size: tuple[int, int] = (512, 512)
    outline_thickness: int = 2
    outline_color: tuple[int, int, int] = (0, 255, 0)
    region_opacity: int = 50  # 0–100 percent
    detections_color: tuple[int, int, int] = (255, 0, 0)

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
        if "fov_size" in data:
            v = data["fov_size"]
            s.fov_size = (int(v[0]), int(v[1]))
        if "outline_thickness" in data:
            s.outline_thickness = int(data["outline_thickness"])
        if "outline_color" in data:
            v = data["outline_color"]
            s.outline_color = (int(v[0]), int(v[1]), int(v[2]))
        if "region_opacity" in data:
            s.region_opacity = max(0, min(100, int(data["region_opacity"])))
        if "detections_color" in data:
            v = data["detections_color"]
            s.detections_color = (int(v[0]), int(v[1]), int(v[2]))
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
