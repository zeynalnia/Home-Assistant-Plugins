"""Shared fixtures for tests."""

import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def patch_state_paths(tmp_path, monkeypatch):
    """Redirect state module paths to a temporary directory."""
    import state

    data_dir = tmp_path / "data"
    data_dir.mkdir()

    monkeypatch.setattr(state, "DATA_DIR", data_dir)
    monkeypatch.setattr(state, "TOKENS_FILE", data_dir / "tokens.json")
    monkeypatch.setattr(state, "UPLOADED_FILE", data_dir / "uploaded.json")


@pytest.fixture(autouse=True)
def patch_options_path(tmp_path, monkeypatch):
    """Redirect options module path to a temporary directory."""
    import options

    monkeypatch.setattr(options, "OPTIONS_FILE", tmp_path / "data" / "options.json")
