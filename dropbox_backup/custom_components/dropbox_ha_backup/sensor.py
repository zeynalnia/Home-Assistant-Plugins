"""Sensor platform for the Dropbox Backup integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DropboxBackupCoordinator


def _parse_iso(val: str | None) -> datetime | None:
    """Parse an ISO-8601 datetime string or return None."""
    if val is None:
        return None
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _fmt_timestamp(val: str | None) -> str | None:
    """Format an ISO-8601 string into a human-readable local timestamp."""
    dt = _parse_iso(val)
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


@dataclass(frozen=True, kw_only=True)
class DropboxBackupSensorDescription(SensorEntityDescription):
    """Describe a Dropbox Backup sensor."""

    value_fn: Callable[[dict], str | int | datetime | None]
    attr_fn: Callable[[dict], dict] | None = None


SENSOR_DESCRIPTIONS: tuple[DropboxBackupSensorDescription, ...] = (
    DropboxBackupSensorDescription(
        key="status",
        translation_key="status",
        name="Status",
        icon="mdi:dropbox",
        value_fn=lambda data: data.get("state", "unknown"),
        attr_fn=lambda data: {
            "uploaded_count": len((data.get("last_result") or {}).get("uploaded", [])),
            "skipped_count": len((data.get("last_result") or {}).get("skipped", [])),
            "error_count": len((data.get("last_result") or {}).get("errors", [])),
            "errors": (data.get("last_result") or {}).get("errors", []),
            "interval_hours": data.get("interval_hours"),
        },
    ),
    DropboxBackupSensorDescription(
        key="last_run",
        translation_key="last_run",
        name="Last Run",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: _parse_iso(data.get("last_run")),
    ),
    DropboxBackupSensorDescription(
        key="next_run",
        translation_key="next_run",
        name="Next Run",
        icon="mdi:calendar-clock",
        value_fn=lambda data: (
            "Manual"
            if data.get("automatic_backup") is False
            else _fmt_timestamp(data.get("next_run"))
        ),
    ),
    DropboxBackupSensorDescription(
        key="uploaded_count",
        translation_key="uploaded_count",
        name="Uploaded Count",
        icon="mdi:cloud-upload",
        value_fn=lambda data: len((data.get("last_result") or {}).get("uploaded", [])),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dropbox Backup sensors from a config entry."""
    coordinator: DropboxBackupCoordinator = hass.data[DOMAIN][entry.entry_id]
    addon_slug = entry.data["addon_slug"]

    async_add_entities(
        DropboxBackupSensor(coordinator, description, addon_slug)
        for description in SENSOR_DESCRIPTIONS
    )


class DropboxBackupSensor(
    CoordinatorEntity[DropboxBackupCoordinator], SensorEntity
):
    """Representation of a Dropbox Backup sensor."""

    entity_description: DropboxBackupSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DropboxBackupCoordinator,
        description: DropboxBackupSensorDescription,
        addon_slug: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{addon_slug}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, addon_slug)},
            name="Dropbox HA Backup",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> str | int | datetime | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return extra state attributes."""
        if (
            self.entity_description.attr_fn is not None
            and self.coordinator.data is not None
        ):
            return self.entity_description.attr_fn(self.coordinator.data)
        return None
