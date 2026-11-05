from __future__ import annotations

from collections import OrderedDict
from threading import Lock

from .config import CACHE_SIZE


class LRUCache:
    def __init__(self, size: int = CACHE_SIZE) -> None:
        self.size = size
        self._data: OrderedDict[str, dict] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> dict | None:
        with self._lock:
            if key not in self._data:
                return None
            self._data.move_to_end(key)
            return self._data[key]

    def set(self, key: str, value: dict) -> None:
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self.size:
                self._data.popitem(last=False)


cache = LRUCache()
