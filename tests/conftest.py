from __future__ import annotations

import os

# Must be set before PySide6 is imported anywhere, so tests can run on
# headless CI runners without a display server.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])
