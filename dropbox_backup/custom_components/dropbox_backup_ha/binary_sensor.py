"""Binary sensor platform for the Dropbox Backup integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DropboxBackupCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dropbox Backup binary sensors from a config entry."""
    coordinator: DropboxBackupCoordinator = hass.data[DOMAIN][entry.entry_id]
    addon_slug = entry.data["addon_slug"]
    async_add_entities([DropboxBackupAuthorizedSensor(coordinator, addon_slug)])


class DropboxBackupAuthorizedSensor(
    CoordinatorEntity[DropboxBackupCoordinator], BinarySensorEntity
):
    """Binary sensor indicating Dropbox authorization status."""

    _attr_has_entity_name = True
    _attr_name = "Authorized"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        coordinator: DropboxBackupCoordinator,
        addon_slug: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{addon_slug}_authorized"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, addon_slug)},
            name="Dropbox Backup",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if authorized."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("authorized", False)
