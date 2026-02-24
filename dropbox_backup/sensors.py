"""Publish sensor entities to Home Assistant via the Supervisor API."""

import logging
import os

import aiohttp

_logger = logging.getLogger(__name__)

SUPERVISOR_URL = "http://supervisor"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
ENTITY_ID = "sensor.dropbox_backup_status"


async def update_sensors(state: str, scheduler, auth) -> None:
    """POST entity state to the HA Core REST API via Supervisor proxy."""
    attributes = {
        "friendly_name": "Dropbox Backup Status",
        "icon": "mdi:dropbox",
        "interval_hours": scheduler.interval_hours,
        "last_run": (
            scheduler.last_run.isoformat() if scheduler.last_run else None
        ),
        "next_run": (
            scheduler.next_run.isoformat() if scheduler.next_run else None
        ),
    }

    result = scheduler.last_result or {}
    attributes["uploaded_count"] = len(result.get("uploaded", []))
    attributes["skipped_count"] = len(result.get("skipped", []))
    errors = result.get("errors", [])
    attributes["error_count"] = len(errors)
    attributes["errors"] = errors

    url = f"{SUPERVISOR_URL}/core/api/states/{ENTITY_ID}"
    headers = {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"state": state, "attributes": attributes}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status not in (200, 201):
                    _logger.warning(
                        "Failed to update %s: HTTP %s", ENTITY_ID, resp.status
                    )
                else:
                    _logger.info("Updated %s to '%s'", ENTITY_ID, state)
    except Exception as exc:
        _logger.warning("Could not update %s: %s", ENTITY_ID, exc)
