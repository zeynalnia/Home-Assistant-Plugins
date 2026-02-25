"""Tests for the state module."""

import json

import state


def test_load_tokens_returns_none_when_missing():
    """load_tokens returns None if the tokens file does not exist."""
    assert state.load_tokens() is None


def test_save_and_load_tokens():
    """Round-trip: save_tokens then load_tokens returns the same dict."""
    tokens = {
        "access_token": "abc123",
        "refresh_token": "def456",
        "expires_at": "2025-01-01T00:00:00",
    }
    state.save_tokens(tokens)
    loaded = state.load_tokens()
    assert loaded == tokens


def test_clear_tokens():
    """clear_tokens removes the tokens file."""
    state.save_tokens({"access_token": "x", "refresh_token": "y"})
    assert state.load_tokens() is not None
    state.clear_tokens()
    assert state.load_tokens() is None


def test_clear_tokens_noop_when_missing():
    """clear_tokens does not raise if the file does not exist."""
    state.clear_tokens()


def test_load_tokens_returns_none_on_corrupt_json():
    """load_tokens returns None if the file contains invalid JSON."""
    state.TOKENS_FILE.write_text("not json!")
    assert state.load_tokens() is None


def test_load_uploaded_returns_empty_when_missing():
    """load_uploaded returns empty dict if the file does not exist."""
    assert state.load_uploaded() == {}


def test_save_and_load_uploaded():
    """Round-trip: save_uploaded then load_uploaded returns the same dict."""
    uploaded = {
        "slug1": {
            "name": "backup1",
            "date": "2025-01-01",
            "dropbox_path": "/backups/backup1.tar",
        }
    }
    state.save_uploaded(uploaded)
    loaded = state.load_uploaded()
    assert loaded == uploaded


def test_load_uploaded_returns_empty_on_corrupt_json():
    """load_uploaded returns empty dict on invalid JSON."""
    state.UPLOADED_FILE.write_text("{bad")
    assert state.load_uploaded() == {}


def test_save_uploaded_creates_data_dir(tmp_path, monkeypatch):
    """save_uploaded creates the DATA_DIR if it does not exist."""
    new_dir = tmp_path / "new_data"
    monkeypatch.setattr(state, "DATA_DIR", new_dir)
    monkeypatch.setattr(state, "UPLOADED_FILE", new_dir / "uploaded.json")
    state.save_uploaded({"slug": {"name": "test"}})
    assert new_dir.exists()
    assert json.loads((new_dir / "uploaded.json").read_text()) == {
        "slug": {"name": "test"}
    }
