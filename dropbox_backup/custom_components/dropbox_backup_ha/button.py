"""Button platform for the Dropbox Backup integration."""

from __future__ import annotations

import logging

import aiohttp

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DropboxBackupCoordinator

_logger = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dropbox Backup button from a config entry."""
    coordinator: DropboxBackupCoordinator = hass.data[DOMAIN][entry.entry_id]
    addon_slug = entry.data["addon_slug"]
    async_add_entities([DropboxBackupTriggerButton(coordinator, addon_slug)])


class DropboxBackupTriggerButton(
    CoordinatorEntity[DropboxBackupCoordinator], ButtonEntity
):
    """Button to trigger a Dropbox backup."""

    _attr_has_entity_name = True
    _attr_name = "Trigger Backup"
    _attr_icon = "mdi:cloud-upload"

    def __init__(
        self,
        coordinator: DropboxBackupCoordinator,
        addon_slug: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{addon_slug}_trigger_backup"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, addon_slug)},
            name="Dropbox HA Backup",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_press(self) -> None:
        """Trigger a backup via the addon API."""
        session = async_get_clientsession(self.hass)
        url = f"{self.coordinator._base_url}/trigger"
        try:
            async with session.post(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                resp.raise_for_status()
        except (aiohttp.ClientError, TimeoutError) as err:
            _logger.error("Failed to trigger backup: %s", err)
            raise
        await self.coordinator.async_request_refresh()
