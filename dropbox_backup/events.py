"""Fire events on the Home Assistant event bus via the Supervisor API."""

import logging
import os

import aiohttp

_logger = logging.getLogger(__name__)

SUPERVISOR_URL = "http://supervisor"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")


async def fire_event(event_type: str, data: dict) -> None:
    """POST an event to the HA event bus through the Supervisor proxy."""
    url = f"{SUPERVISOR_URL}/core/api/events/{event_type}"
    headers = {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as resp:
                if resp.status != 200:
                    _logger.warning(
                        "Failed to fire event %s: HTTP %s", event_type, resp.status
                    )
                else:
                    _logger.info("Fired event %s", event_type)
    except Exception as exc:
        _logger.warning("Could not fire event %s: %s", event_type, exc)
