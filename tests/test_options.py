"""Tests for the options module."""

import json

import options


def test_load_options_returns_empty_when_missing():
    """load_options returns empty dict if options file does not exist."""
    assert options.load_options() == {}


def test_load_options_reads_json():
    """load_options returns the parsed JSON content."""
    opts = {
        "dropbox_app_key": "key123",
        "dropbox_app_secret": "secret456",
        "automatic_backup": True,
        "backup_interval_hours": 12,
        "max_backups_in_dropbox": 5,
        "dropbox_backup_path": "/HA/Backups",
    }
    options.OPTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    options.OPTIONS_FILE.write_text(json.dumps(opts))
    loaded = options.load_options()
    assert loaded == opts


def test_load_options_returns_empty_on_corrupt_json():
    """load_options returns empty dict on invalid JSON."""
    options.OPTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    options.OPTIONS_FILE.write_text("not valid json")
    assert options.load_options() == {}
