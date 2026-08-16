"""Render the platform icon files from the app's own icon code.

The icon is drawn programmatically in ``slideannotator.ui.app_icon``; rendering
the installer icons from that same function keeps the Finder/taskbar icon and
the in-app icon from ever drifting apart.

Outputs (next to this file):
  SlideAnnotator.icns  macOS bundle icon
  SlideAnnotator.ico   Windows executable/installer icon
  SlideAnnotator.png   512px, for the Linux .desktop entry

Usage: uv run python packaging/make_icons.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from PySide6.QtWidgets import QApplication  # noqa: E402

from slideannotator.ui.app_icon import _draw  # noqa: E402

# (base size, is_retina) pairs required by iconutil.
ICNS_SIZES = [16, 32, 128, 256, 512]
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def _write_png(size: int, path: Path) -> None:
    if not _draw(size).save(str(path), "PNG"):
        raise RuntimeError(f"failed to render {path}")


def build_icns(out: Path) -> None:
    if not shutil.which("iconutil"):
        print("skip .icns: iconutil not available (macOS only)")
        return
    iconset = out.with_suffix(".iconset")
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True)
    for size in ICNS_SIZES:
        _write_png(size, iconset / f"icon_{size}x{size}.png")
        _write_png(size * 2, iconset / f"icon_{size}x{size}@2x.png")
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out)], check=True)
    shutil.rmtree(iconset)
    print(f"wrote {out}")


def build_ico(out: Path) -> None:
    from PIL import Image

    tmp = out.parent / "_icon_1024.png"
    _write_png(1024, tmp)
    Image.open(tmp).save(out, sizes=[(s, s) for s in ICO_SIZES])
    tmp.unlink()
    print(f"wrote {out}")


def build_png(out: Path) -> None:
    _write_png(512, out)
    print(f"wrote {out}")


def main() -> None:
    QApplication([])  # QPixmap needs a running Qt application
    build_icns(HERE / "SlideAnnotator.icns")
    build_ico(HERE / "SlideAnnotator.ico")
    build_png(HERE / "SlideAnnotator.png")


if __name__ == "__main__":
    main()
