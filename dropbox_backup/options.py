"""Load addon options from Home Assistant."""

import json
import logging
from pathlib import Path

OPTIONS_FILE = Path("/data/options.json")

_logger = logging.getLogger(__name__)


def load_options() -> dict:
    """Load addon options. Returns dict with all configured values."""
    if not OPTIONS_FILE.exists():
        _logger.warning("Options file not found at %s", OPTIONS_FILE)
        return {}
    try:
        return json.loads(OPTIONS_FILE.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        _logger.error("Failed to load options: %s", exc)
        return {}
