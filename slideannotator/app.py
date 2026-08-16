from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from . import __version__
from .ui.app_icon import make_app_icon
from .ui.main_window import MainWindow


def main() -> None:
    if "--version" in sys.argv:
        print(__version__)
        return
    if "--self-test" in sys.argv:
        from .selftest import run

        sys.exit(run())

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(name)-30s  %(levelname)s  %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    logging.getLogger("pyvips").setLevel(logging.WARNING)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("SlideAnnotator")
    app.setApplicationVersion(__version__)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    app.setWindowIcon(make_app_icon())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
