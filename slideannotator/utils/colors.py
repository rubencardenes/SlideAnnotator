CHANNEL_COLORS: dict[str, tuple[int, int, int]] = {
    "dapi": (0, 102, 255),
    "hoechst": (0, 102, 255),
    "fitc": (0, 255, 0),
    "gfp": (0, 255, 0),
    "cy3": (255, 165, 0),
    "tritc": (255, 69, 0),
    "cy5": (255, 0, 0),
    "alexa647": (255, 0, 0),
    "cy7": (255, 0, 255),
    "alexa488": (0, 220, 80),
    "pe": (255, 100, 0),
    "af488": (0, 220, 80),
    "af555": (255, 165, 0),
    "af647": (255, 0, 0),
    "af750": (180, 0, 255),
}

_FALLBACK_COLORS: list[tuple[int, int, int]] = [
    (0, 255, 100),
    (255, 255, 0),
    (0, 200, 255),
    (255, 128, 0),
    (200, 0, 255),
    (255, 0, 128),
    (0, 255, 200),
    (128, 255, 0),
    (255, 200, 0),
    (100, 100, 255),
    (0, 128, 128),
    (255, 255, 255),
]


def assign_channel_color(name: str, index: int) -> tuple[int, int, int]:
    key = name.lower().replace(" ", "").replace("-", "").replace("_", "")
    for pattern, color in CHANNEL_COLORS.items():
        if pattern in key or key.startswith(pattern):
            return color
    return _FALLBACK_COLORS[index % len(_FALLBACK_COLORS)]
