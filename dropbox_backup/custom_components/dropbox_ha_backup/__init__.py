"""The Dropbox Backup integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant

from .const import DOMAIN, EVENT_BACKUP_FAILED, EVENT_BACKUP_SUCCESS
from .coordinator import DropboxBackupCoordinator

_logger = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dropbox Backup from a config entry."""
    base_url = entry.data["base_url"]

    coordinator = DropboxBackupCoordinator(hass, entry, base_url)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def _handle_backup_event(event: Event) -> None:
        """Refresh coordinator when a backup event fires."""
        _logger.debug("Received event %s, refreshing coordinator", event.event_type)
        await coordinator.async_request_refresh()

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_BACKUP_SUCCESS, _handle_backup_event)
    )
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_BACKUP_FAILED, _handle_backup_event)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
