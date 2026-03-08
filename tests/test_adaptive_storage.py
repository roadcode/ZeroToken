"""Tests for adaptive fingerprint storage."""

import pytest

from zerotoken.adaptive_storage import AdaptiveStorage


class TestAdaptiveStorage:
    """AdaptiveStorage save/load/delete and overwrite."""

    @pytest.fixture
    def storage(self, tmp_path):
        db_path = str(tmp_path / "test_adaptive.db")
        return AdaptiveStorage(db_path=db_path)

    def test_save_and_load(self, storage):
        fp = {"parent": {"tag": "div"}, "self": {"tag": "a", "text": "Link"}}
        storage.save("example.com", "#btn", fp)
        loaded = storage.load("example.com", "#btn")
        assert loaded is not None
        assert loaded["parent"]["tag"] == "div"
        assert loaded["self"]["text"] == "Link"

    def test_load_missing_returns_none(self, storage):
        assert storage.load("example.com", "#nonexistent") is None

    def test_save_overwrites(self, storage):
        storage.save("example.com", "id1", {"v": 1})
        storage.save("example.com", "id1", {"v": 2})
        loaded = storage.load("example.com", "id1")
        assert loaded == {"v": 2}

    def test_delete_removes_and_returns_true(self, storage):
        storage.save("example.com", "id1", {"v": 1})
        assert storage.delete("example.com", "id1") is True
        assert storage.load("example.com", "id1") is None

    def test_delete_missing_returns_false(self, storage):
        assert storage.delete("example.com", "id1") is False

    def test_different_domains_isolated(self, storage):
        storage.save("a.com", "sel", {"x": 1})
        storage.save("b.com", "sel", {"x": 2})
        assert storage.load("a.com", "sel") == {"x": 1}
        assert storage.load("b.com", "sel") == {"x": 2}
