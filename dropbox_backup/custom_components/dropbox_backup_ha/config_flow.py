"""Config flow for the Dropbox Backup integration."""

from __future__ import annotations

import logging
import os
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.components.hassio import is_hassio
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ADDON_SLUG_SUFFIX, DEFAULT_PORT, DOMAIN

_logger = logging.getLogger(__name__)


class DropboxBackupConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dropbox Backup."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._addon_slug: str | None = None
        self._hostname: str | None = None
        self._port: int = DEFAULT_PORT

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if is_hassio(self.hass):
            addon_info = await self._find_addon()
            if addon_info:
                return await self.async_step_confirm()
        return await self.async_step_manual()

    async def _find_addon(self) -> dict | None:
        """Query the Supervisor API for the Dropbox Backup addon."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                "http://supervisor/addons",
                headers={"Authorization": "Bearer " + self._get_supervisor_token()},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except (aiohttp.ClientError, TimeoutError):
            _logger.debug("Failed to query Supervisor addons API")
            return None

        for addon in data.get("data", {}).get("addons", []):
            slug = addon.get("slug", "")
            if slug.endswith(ADDON_SLUG_SUFFIX):
                self._addon_slug = slug
                self._hostname = slug.replace("_", "-")
                self._port = DEFAULT_PORT
                return addon
        return None

    @staticmethod
    def _get_supervisor_token() -> str:
        """Get the Supervisor API token from the environment."""
        return os.environ.get("SUPERVISOR_TOKEN", "")

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm auto-discovered addon."""
        if self._addon_slug is None:
            return self.async_abort(reason="addon_not_found")
        await self.async_set_unique_id(self._addon_slug)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            base_url = f"http://{self._hostname}:{self._port}"
            if not await self._validate_connection(base_url):
                return self.async_show_form(
                    step_id="confirm",
                    errors={"base": "cannot_connect"},
                )
            return self.async_create_entry(
                title="Dropbox Backup",
                data={
                    "addon_slug": self._addon_slug,
                    "hostname": self._hostname,
                    "port": self._port,
                    "base_url": base_url,
                },
            )

        return self.async_show_form(step_id="confirm")

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            hostname = user_input["hostname"]
            port = user_input["port"]
            base_url = f"http://{hostname}:{port}"

            if not await self._validate_connection(base_url):
                errors["base"] = "cannot_connect"
            else:
                addon_slug = user_input.get("addon_slug", f"local_{ADDON_SLUG_SUFFIX}")
                await self.async_set_unique_id(addon_slug)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Dropbox Backup",
                    data={
                        "addon_slug": addon_slug,
                        "hostname": hostname,
                        "port": port,
                        "base_url": base_url,
                    },
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required("hostname"): str,
                    vol.Required("port", default=DEFAULT_PORT): int,
                    vol.Optional("addon_slug", default=f"local_{ADDON_SLUG_SUFFIX}"): str,
                }
            ),
            errors=errors,
        )

    async def _validate_connection(self, base_url: str) -> bool:
        """Validate we can connect to the addon's /status endpoint."""
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                f"{base_url}/status",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                return resp.status == 200
        except (aiohttp.ClientError, TimeoutError):
            return False
