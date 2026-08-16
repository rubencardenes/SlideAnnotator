"""Headless integrity check for a packaged build.

Exercises every native dependency that a PyInstaller bundle can plausibly get
wrong — libvips, the ONNX runtime, the CZI/HDF5 readers, the Qt platform plugin
— so CI can fail a broken installer instead of publishing it.

Run as ``SlideAnnotator --self-test``; exits 0 on success, 1 on the first
failure.
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path

_checks: list[tuple[str, object]] = []


def _check(name):
    def register(fn):
        _checks.append((name, fn))
        return fn

    return register


@_check("pyvips / libvips")
def _check_pyvips() -> str:
    import pyvips

    version = ".".join(str(pyvips.base.version(i)) for i in range(3))
    image = pyvips.Image.black(64, 64) + 128
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "probe.tif"
        image.tiffsave(str(out), pyramid=True, tile=True, compression="deflate")
        reopened = pyvips.Image.new_from_file(str(out))
        if (reopened.width, reopened.height) != (64, 64):
            raise RuntimeError("round-tripped TIFF has unexpected dimensions")
    return f"libvips {version} (API mode: {pyvips.API_mode})"


@_check("onnxruntime + bundled StarDist model")
def _check_onnx() -> str:
    import onnxruntime

    from .settings import bundled_stardist_model

    model = bundled_stardist_model()
    if model is None:
        raise RuntimeError("bundled StarDist model is missing from this build")
    session = onnxruntime.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    inputs = [i.name for i in session.get_inputs()]
    return f"onnxruntime {onnxruntime.__version__}, model inputs={inputs}"


@_check("readers (CZI / HDF5 / TIFF)")
def _check_readers() -> str:
    import h5py
    import pylibCZIrw.czi as pyczi

    from .readers import czi, ims, ome_tif  # noqa: F401

    return f"h5py {h5py.__version__}, pylibCZIrw ({pyczi.__name__}), readers importable"


@_check("StarDist NMS extension")
def _check_nms() -> str:
    from .inference.nms import NMSExtensionUnavailable, _nms_ext

    try:
        _nms_ext("stardist2d")
    except NMSExtensionUnavailable as e:
        # Expected off macOS/arm64. Not a build failure, but it must degrade
        # through the documented error rather than crash.
        return f"unavailable, degrades cleanly ({e.__class__.__name__})"
    return "available"


@_check("matplotlib Qt backend")
def _check_matplotlib() -> str:
    import matplotlib

    matplotlib.use("QtAgg")
    from matplotlib.backends import backend_qtagg  # noqa: F401

    return f"matplotlib {matplotlib.__version__}"


@_check("Qt application + main window")
def _check_qt() -> str:
    from PySide6.QtWidgets import QApplication

    from .ui.app_icon import make_app_icon
    from .ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    app.setWindowIcon(make_app_icon())
    window = MainWindow()
    window.close()
    return f"Qt platform: {app.platformName()}"


def run() -> int:
    """Run every check, printing a report. Returns a process exit code."""
    from . import __version__

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    print(f"SlideAnnotator {__version__} self-test")
    print(f"  python  {sys.version.split()[0]} ({sys.platform})")
    print(f"  frozen  {getattr(sys, 'frozen', False)}")
    print()

    failures = 0
    for name, check in _checks:
        try:
            detail = check()
        except Exception:
            failures += 1
            print(f"  FAIL  {name}")
            print(traceback.format_exc())
        else:
            print(f"  ok    {name}: {detail}")

    print()
    if failures:
        print(f"self-test FAILED ({failures}/{len(_checks)} checks)")
        return 1
    print(f"self-test passed ({len(_checks)} checks)")
    return 0
