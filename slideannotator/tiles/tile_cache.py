from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class TileKey:
    path: str
    level: int
    tile_x: int
    tile_y: int


class LRUCache:
    """Thread-safe LRU cache keyed by TileKey."""

    def __init__(self, max_size: int = 300) -> None:
        self._max = max_size
        self._data: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: TileKey):
        with self._lock:
            if key not in self._data:
                return None
            self._data.move_to_end(key)
            return self._data[key]

    def put(self, key: TileKey, value) -> None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = value
            if len(self._data) > self._max:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __contains__(self, key: TileKey) -> bool:
        with self._lock:
            return key in self._data
