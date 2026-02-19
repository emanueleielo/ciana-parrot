"""Simple JSON file-backed persistent store."""

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class JsonStore:
    """Thread-safe JSON file store for persisting small state across restarts.

    Usage:
        store = JsonStore("data/my_state.json")
        store.set("user_123", {"mode": "active", "project": "foo"})
        data = store.get("user_123")  # -> dict or None
        store.delete("user_123")
        all_data = store.all()  # -> full dict
    """

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._data: dict[str, Any] = self._load()

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def delete(self, key: str) -> None:
        if self._data.pop(key, None) is not None:
            self._save()

    def all(self) -> dict[str, Any]:
        return dict(self._data)

    def update(self, data: dict[str, Any]) -> None:
        """Merge multiple keys and save once."""
        self._data.update(data)
        self._save()

    def clear(self) -> None:
        if self._data:
            self._data.clear()
            self._save()

    def _load(self) -> dict:
        try:
            if self._path.exists():
                return json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not load %s: %s", self._path, e)
        return {}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data, indent=2))
        except OSError as e:
            logger.warning("Could not save %s: %s", self._path, e)
