from __future__ import annotations

from slideannotator.ui.main_window import MainWindow


def test_main_window_instantiates_headless(qapp) -> None:
    window = MainWindow()
    try:
        assert window.windowTitle() == "SlideAnnotator"
    finally:
        window.close()
