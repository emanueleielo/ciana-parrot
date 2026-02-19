"""Tests for src.store — JsonStore CRUD, persistence, corruption recovery."""

import json

from src.store import JsonStore


class TestJsonStore:
    def test_get_set(self, tmp_path):
        store = JsonStore(tmp_path / "store.json")
        store.set("key1", {"a": 1})
        assert store.get("key1") == {"a": 1}

    def test_get_default(self, tmp_path):
        store = JsonStore(tmp_path / "store.json")
        assert store.get("missing") is None
        assert store.get("missing", "default") == "default"

    def test_delete(self, tmp_path):
        store = JsonStore(tmp_path / "store.json")
        store.set("k", "v")
        store.delete("k")
        assert store.get("k") is None

    def test_delete_nonexistent(self, tmp_path):
        store = JsonStore(tmp_path / "store.json")
        store.delete("nope")  # should not raise

    def test_all(self, tmp_path):
        store = JsonStore(tmp_path / "store.json")
        store.set("a", 1)
        store.set("b", 2)
        result = store.all()
        assert result == {"a": 1, "b": 2}
        # Returned dict should be a copy
        result["c"] = 3
        assert store.get("c") is None

    def test_update(self, tmp_path):
        store = JsonStore(tmp_path / "store.json")
        store.set("a", 1)
        store.update({"b": 2, "c": 3})
        assert store.get("a") == 1
        assert store.get("b") == 2
        assert store.get("c") == 3

    def test_clear(self, tmp_path):
        store = JsonStore(tmp_path / "store.json")
        store.set("k", "v")
        store.clear()
        assert store.all() == {}

    def test_clear_empty(self, tmp_path):
        store = JsonStore(tmp_path / "store.json")
        store.clear()  # should not raise

    def test_persistence(self, tmp_path):
        path = tmp_path / "store.json"
        store1 = JsonStore(path)
        store1.set("key", "value")
        # New instance reads from disk
        store2 = JsonStore(path)
        assert store2.get("key") == "value"

    def test_corruption_recovery(self, tmp_path):
        path = tmp_path / "store.json"
        path.write_text("not valid json{{{")
        store = JsonStore(path)
        assert store.all() == {}
        # Should still work after recovery
        store.set("k", "v")
        assert store.get("k") == "v"

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "sub" / "dir" / "store.json"
        store = JsonStore(path)
        store.set("k", "v")
        assert path.exists()
        assert json.loads(path.read_text()) == {"k": "v"}

    def test_file_not_exist_on_init(self, tmp_path):
        store = JsonStore(tmp_path / "new.json")
        assert store.all() == {}

    def test_overwrite_value(self, tmp_path):
        store = JsonStore(tmp_path / "store.json")
        store.set("k", "old")
        store.set("k", "new")
        assert store.get("k") == "new"
