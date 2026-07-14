"""Train/test grouping of slides based on their location on disk."""

from __future__ import annotations

from pathlib import Path

TRAIN = "train"
TEST = "test"
GROUPS = (TRAIN, TEST)

SLIDE_SUFFIXES = (".ome.tif", ".ome.tiff", ".ims", ".czi")


def is_slide_file(path: Path) -> bool:
    """True if ``path`` looks like a slide file (and not a derived mask)."""
    low = path.name.lower()
    return any(low.endswith(s) for s in SLIDE_SUFFIXES) and "mask" not in low


def classify_group(path: Path | None, root: Path) -> str:
    """Return ``"train"`` or ``"test"`` for a slide located under ``root``.

    A slide is a test slide if any directory component of its path (relative to
    ``root``) is named ``test``; it is a train slide if a component is named
    ``train``. The shallowest matching component wins. Anything else — including
    slides with no recorded path or in no ``train``/``test`` subfolder —
    defaults to ``train``.
    """
    if path is None:
        return TRAIN
    try:
        rel = path.relative_to(root)
    except ValueError:
        return TRAIN
    for part in rel.parts[:-1]:  # directory components only, shallow → deep
        low = part.lower()
        if low in GROUPS:
            return low
    return TRAIN


def scan_slide_files(root: Path) -> dict[str, Path]:
    """Map each slide file's stem under ``root`` to its path on disk.

    When two files share a stem the last one encountered wins.
    """
    result: dict[str, Path] = {}
    root = Path(root).expanduser().resolve()
    if not root.exists():
        return result
    for p in root.rglob("*"):
        if p.is_file() and is_slide_file(p):
            result[p.stem] = p
    return result


def scan_slide_groups(root: Path) -> dict[str, str]:
    """Map each slide file's stem under ``root`` to its train/test group.

    Groups are derived from where the file actually lives on disk (which may
    differ from a stale path recorded in the database), so callers get the same
    train/test split the image list panel shows.
    """
    root = Path(root).expanduser().resolve()
    return {stem: classify_group(p, root) for stem, p in scan_slide_files(root).items()}
