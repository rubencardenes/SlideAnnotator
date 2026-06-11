from __future__ import annotations

import json
from pathlib import Path

from .compositing.compositor import ChannelSettings
from .readers.protocol import ChannelInfo

_FILENAME = "viewsettings.json"


def view_settings_path(image_path: Path) -> Path:
    return image_path.parent / _FILENAME


def save_view_settings(
    image_path: Path,
    channels: list[ChannelInfo],
    settings: list[ChannelSettings],
) -> None:
    data = {
        "channels": [
            {"name": ch.name, "visible": s.visible, "min": s.min_val, "max": s.max_val}
            for ch, s in zip(channels, settings)
        ]
    }
    view_settings_path(image_path).write_text(json.dumps(data, indent=2))


def load_view_settings(
    image_path: Path,
    channels: list[ChannelInfo],
    settings: list[ChannelSettings],
) -> bool:
    """Apply saved view settings in-place. Returns True if anything was applied."""
    path = view_settings_path(image_path)
    if not path.exists():
        return False
    try:
        raw = json.loads(path.read_text())
    except Exception:
        return False
    saved = {item["name"]: item for item in raw.get("channels", [])}
    applied = False
    for ch, s in zip(channels, settings):
        if ch.name in saved:
            item = saved[ch.name]
            s.visible = bool(item.get("visible", s.visible))
            s.min_val = float(item.get("min", s.min_val))
            s.max_val = float(item.get("max", s.max_val))
            applied = True
    return applied
