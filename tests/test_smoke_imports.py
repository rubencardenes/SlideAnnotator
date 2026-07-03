from __future__ import annotations

import importlib
import pkgutil

import pytest

import slideannotator

_MODULE_NAMES = [
    info.name for info in pkgutil.walk_packages(slideannotator.__path__, prefix="slideannotator.")
]


@pytest.mark.parametrize("module_name", _MODULE_NAMES)
def test_import_module(module_name: str) -> None:
    importlib.import_module(module_name)
