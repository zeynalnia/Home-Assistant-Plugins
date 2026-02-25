"""DataUpdateCoordinator for the Dropbox Backup integration."""

from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_logger = logging.getLogger(__name__)


class DropboxBackupCoordinator(DataUpdateCoordinator[dict]):
    """Polls the addon /status endpoint."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, base_url: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _logger,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._base_url = base_url

    async def _async_update_data(self) -> dict:
        """Fetch status from the addon."""
        session = async_get_clientsession(self.hass)
        url = f"{self._base_url}/status"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                resp.raise_for_status()
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Error communicating with addon: {err}") from err
