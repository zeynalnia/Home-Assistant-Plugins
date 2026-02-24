"""Persistent state management for tokens and upload tracking."""

import json
import logging
from pathlib import Path

DATA_DIR = Path("/data")
TOKENS_FILE = DATA_DIR / "tokens.json"
UPLOADED_FILE = DATA_DIR / "uploaded.json"

_logger = logging.getLogger(__name__)


def load_tokens() -> dict | None:
    """Load OAuth tokens from disk. Returns None if not found."""
    if not TOKENS_FILE.exists():
        return None
    try:
        return json.loads(TOKENS_FILE.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        _logger.error("Failed to load tokens: %s", exc)
        return None


def save_tokens(tokens: dict) -> None:
    """Save OAuth tokens to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TOKENS_FILE.write_text(json.dumps(tokens, indent=2))


def clear_tokens() -> None:
    """Remove stored tokens."""
    if TOKENS_FILE.exists():
        TOKENS_FILE.unlink()


def load_uploaded() -> dict:
    """Load uploaded backup tracking. Returns {slug: {name, date, path}}."""
    if not UPLOADED_FILE.exists():
        return {}
    try:
        return json.loads(UPLOADED_FILE.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        _logger.error("Failed to load uploaded state: %s", exc)
        return {}


def save_uploaded(uploaded: dict) -> None:
    """Save uploaded backup tracking to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADED_FILE.write_text(json.dumps(uploaded, indent=2))
