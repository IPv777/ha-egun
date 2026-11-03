"""The eGun integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    ACTION_MUTE_ITEM,
    CONF_MAX_PRICE,
    DOMAIN,
)
from .coordinator import EgunCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

SERVICE_REFRESH = "refresh"
SERVICE_SET_BUDGET = "set_budget"
SERVICE_MUTE_ITEM = "mute_item"
SERVICE_UNMUTE_ITEM = "unmute_item"
SERVICE_RESET_CACHE = "reset_cache"

SCHEMA_SET_BUDGET = vol.Schema(
    {
        vol.Required("max_price"): vol.Coerce(float),
        vol.Optional("entry_id"): cv.string,
    }
)

SCHEMA_MUTE_ITEM = vol.Schema(
    {
        vol.Required("item_id"): cv.string,
        vol.Optional("entry_id"): cv.string,
    }
)

SCHEMA_UNMUTE_ITEM = vol.Schema(
    {
        vol.Required("item_id"): cv.string,
        vol.Optional("entry_id"): cv.string,
    }
)

SCHEMA_ENTRY_ONLY = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up eGun from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = EgunCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Register services on first entry
    if len(hass.data[DOMAIN]) == 1:
        await _async_register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register custom services for eGun."""

    async def handle_refresh(call: ServiceCall) -> None:
        """Handle refresh service call."""
        entry_id = call.data.get("entry_id")
        coordinators = [
            c for c in list(hass.data.get(DOMAIN, {}).values())
            if isinstance(c, EgunCoordinator)
        ]
        for coord in coordinators:
            if not entry_id or coord.entry.entry_id == entry_id:
                _LOGGER.info("Manually refreshing eGun feed: %s", coord.entry.title)
                await coord.async_request_refresh()

    async def handle_set_budget(call: ServiceCall) -> None:
        """Handle set_budget service call."""
        max_price = float(call.data["max_price"])
        entry_id = call.data.get("entry_id")
        entries_to_update = list(hass.config_entries.async_entries(DOMAIN))
        for entry in entries_to_update:
            if not entry_id or entry.entry_id == entry_id:
                _LOGGER.info("Updating budget for eGun %s to %s €", entry.title, max_price)
                new_options = dict(entry.options)
                new_options[CONF_MAX_PRICE] = max_price
                hass.config_entries.async_update_entry(entry, options=new_options)

    async def handle_mute_item(call: ServiceCall) -> None:
        """Handle mute_item service call."""
        item_id = str(call.data["item_id"])
        entry_id = call.data.get("entry_id")
        coordinators = [
            c for c in list(hass.data.get(DOMAIN, {}).values())
            if isinstance(c, EgunCoordinator)
        ]
        for coord in coordinators:
            if not entry_id or coord.entry.entry_id == entry_id:
                await coord.async_mute_item(item_id)

    async def handle_unmute_item(call: ServiceCall) -> None:
        """Handle unmute_item service call."""
        item_id = str(call.data["item_id"])
        entry_id = call.data.get("entry_id")
        coordinators = [
            c for c in list(hass.data.get(DOMAIN, {}).values())
            if isinstance(c, EgunCoordinator)
        ]
        for coord in coordinators:
            if not entry_id or coord.entry.entry_id == entry_id:
                await coord.async_unmute_item(item_id)

    async def handle_reset_cache(call: ServiceCall) -> None:
        """Handle reset_cache service call."""
        entry_id = call.data.get("entry_id")
        coordinators = [
            c for c in list(hass.data.get(DOMAIN, {}).values())
            if isinstance(c, EgunCoordinator)
        ]
        for coord in coordinators:
            if not entry_id or coord.entry.entry_id == entry_id:
                await coord.async_reset_cache()

    async def handle_notification_action(event: Event) -> None:
        """Handle notification action response from companion app."""
        action = event.data.get("action", "")
        if action.startswith(f"{ACTION_MUTE_ITEM}_"):
            item_id = action.replace(f"{ACTION_MUTE_ITEM}_", "")
            _LOGGER.info("Muting eGun item via push notification: %s", item_id)
            coordinators = [
                c for c in list(hass.data.get(DOMAIN, {}).values())
                if isinstance(c, EgunCoordinator)
            ]
            for coord in coordinators:
                await coord.async_mute_item(item_id)

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, handle_refresh, schema=SCHEMA_ENTRY_ONLY)
    hass.services.async_register(DOMAIN, SERVICE_SET_BUDGET, handle_set_budget, schema=SCHEMA_SET_BUDGET)
    hass.services.async_register(DOMAIN, SERVICE_MUTE_ITEM, handle_mute_item, schema=SCHEMA_MUTE_ITEM)
    hass.services.async_register(DOMAIN, SERVICE_UNMUTE_ITEM, handle_unmute_item, schema=SCHEMA_UNMUTE_ITEM)
    hass.services.async_register(DOMAIN, SERVICE_RESET_CACHE, handle_reset_cache, schema=SCHEMA_ENTRY_ONLY)

    hass.bus.async_listen("mobile_app_notification_action", handle_notification_action)
