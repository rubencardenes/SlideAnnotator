# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SlideAnnotator (macOS / Windows / Linux).

Build with:  uv run pyinstaller packaging/slideannotator.spec --noconfirm
"""

import platform
import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"
IS_MAC_ARM = IS_MAC and platform.machine() == "arm64"

sys.path.insert(0, str(ROOT))
from slideannotator import __version__  # noqa: E402

# ---------------------------------------------------------------- data files

datas = [
    # StarDist weights, so nuclei detection works with no configuration.
    (
        str(ROOT / "slideannotator/resources/models/stardist-versatile-fluo_dynamic.onnx"),
        "slideannotator/resources/models",
    ),
]

# --------------------------------------------------------------- binaries

# The prebuilt StarDist NMS extension exists only for macOS/arm64 + CPython 3.12.
# Its .so links libomp as @loader_path/../.dylibs/libomp.dylib, so both files
# must keep that exact relative layout inside the bundle.
binaries = []
hiddenimports = []
if IS_MAC_ARM:
    binaries += [
        (
            str(ROOT / "slideannotator/inference/lib/stardist2d.cpython-312-darwin.so"),
            "slideannotator/inference/lib",
        ),
        (
            str(ROOT / "slideannotator/inference/.dylibs/libomp.dylib"),
            "slideannotator/inference/.dylibs",
        ),
    ]
    # Imported lazily inside a function (inference/nms.py), so invisible to the
    # static analysis.
    hiddenimports += ["slideannotator.inference.lib.stardist2d"]

# ---------------------------------------------------------------- excludes

# Only QtCore/QtGui/QtWidgets are imported anywhere in the app; PySide6 alone is
# 1.2 GB installed, so everything else goes. Anything needed indirectly (e.g. by
# matplotlib's Qt backend) will surface as an ImportError in --self-test.
excludes = [
    "tkinter",
    "PyQt5",
    "PyQt6",
    "IPython",
    "pytest",
    "notebook",
    "sphinx",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
]

# ---------------------------------------------------------------- analysis

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SlideAnnotator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX corrupts signed Mach-O binaries and trips antivirus on Windows
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "packaging/SlideAnnotator.ico") if IS_WIN else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SlideAnnotator",
)

if IS_MAC:
    app = BUNDLE(
        coll,
        name="SlideAnnotator.app",
        icon=str(ROOT / "packaging/SlideAnnotator.icns"),
        bundle_identifier="com.rubencardenes.slideannotator",
        version=__version__,
        info_plist={
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
            "LSApplicationCategoryType": "public.app-category.medical",
            # Slides and their viewsettings.json sidecars usually live in these
            # locations; without the strings macOS denies access silently.
            "NSDocumentsFolderUsageDescription": (
                "SlideAnnotator reads slide images and writes annotations in your Documents folder."
            ),
            "NSDownloadsFolderUsageDescription": (
                "SlideAnnotator reads slide images from your Downloads folder."
            ),
            "NSDesktopFolderUsageDescription": (
                "SlideAnnotator reads slide images from your Desktop."
            ),
            "NSRemovableVolumesUsageDescription": (
                "SlideAnnotator reads slide images from external drives."
            ),
        },
    )
