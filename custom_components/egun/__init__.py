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
        vol.Optional("max_price", default=600.0): vol.Coerce(float),
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

    # Register refresh service if not already registered
    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH):
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

        hass.services.async_register(
            DOMAIN,
            SERVICE_REFRESH,
            handle_refresh,
            schema=SCHEMA_ENTRY_ONLY,
        )

    # Register set_budget service if not already registered
    if not hass.services.has_service(DOMAIN, SERVICE_SET_BUDGET):
        async def handle_set_budget(call: ServiceCall) -> None:
            """Handle set_budget service call safely across config entries."""
            max_price = float(call.data.get("max_price", 600.0))
            entry_id = call.data.get("entry_id")
            _LOGGER.info("Set budget called for eGun with max_price=%.2f (entry_id=%s)", max_price, entry_id)

            entries_to_update: list[ConfigEntry] = []
            if entry_id:
                entry_obj = hass.config_entries.async_get_entry(entry_id)
                if entry_obj and entry_obj.domain == DOMAIN:
                    entries_to_update.append(entry_obj)
            else:
                entries_to_update = list(hass.config_entries.async_entries(DOMAIN))

            for ent in entries_to_update:
                _LOGGER.info("Updating budget for eGun %s to %.2f €", ent.title, max_price)
                new_options = dict(ent.options)
                new_options[CONF_MAX_PRICE] = float(max_price)
                hass.config_entries.async_update_entry(ent, options=new_options)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_BUDGET,
            handle_set_budget,
            schema=SCHEMA_SET_BUDGET,
        )

    # Register mute_item service if not already registered
    if not hass.services.has_service(DOMAIN, SERVICE_MUTE_ITEM):
        async def handle_mute_item(call: ServiceCall) -> None:
            """Handle mute_item service call."""
            item_id = str(call.data["item_id"]).strip()
            entry_id = call.data.get("entry_id")
            coordinators = [
                c for c in list(hass.data.get(DOMAIN, {}).values())
                if isinstance(c, EgunCoordinator)
            ]
            for coord in coordinators:
                if not entry_id or coord.entry.entry_id == entry_id:
                    await coord.async_mute_item(item_id)

        hass.services.async_register(
            DOMAIN,
            SERVICE_MUTE_ITEM,
            handle_mute_item,
            schema=SCHEMA_MUTE_ITEM,
        )

    # Register unmute_item service if not already registered
    if not hass.services.has_service(DOMAIN, SERVICE_UNMUTE_ITEM):
        async def handle_unmute_item(call: ServiceCall) -> None:
            """Handle unmute_item service call."""
            item_id = str(call.data["item_id"]).strip()
            entry_id = call.data.get("entry_id")
            coordinators = [
                c for c in list(hass.data.get(DOMAIN, {}).values())
                if isinstance(c, EgunCoordinator)
            ]
            for coord in coordinators:
                if not entry_id or coord.entry.entry_id == entry_id:
                    await coord.async_unmute_item(item_id)

        hass.services.async_register(
            DOMAIN,
            SERVICE_UNMUTE_ITEM,
            handle_unmute_item,
            schema=SCHEMA_UNMUTE_ITEM,
        )

    # Register reset_cache service if not already registered
    if not hass.services.has_service(DOMAIN, SERVICE_RESET_CACHE):
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

        hass.services.async_register(
            DOMAIN,
            SERVICE_RESET_CACHE,
            handle_reset_cache,
            schema=SCHEMA_ENTRY_ONLY,
        )

    # Register actionable notification listener
    if f"{DOMAIN}_action_listener" not in hass.data[DOMAIN]:
        async def handle_notification_action(event: Event) -> None:
            """Handle notification action response from companion app."""
            action = str(event.data.get("action", ""))
            tag = str(event.data.get("tag", ""))
            item_id = ""
            if action.startswith(f"{ACTION_MUTE_ITEM}_"):
                item_id = action.replace(f"{ACTION_MUTE_ITEM}_", "")
            elif "egun_" in tag and (action == ACTION_MUTE_ITEM or action == "MUTE"):
                item_id = tag.replace("egun_", "")

            if item_id:
                _LOGGER.info("Muting eGun item via push notification: %s", item_id)
                coordinators = [
                    c for c in list(hass.data.get(DOMAIN, {}).values())
                    if isinstance(c, EgunCoordinator)
                ]
                for coord in coordinators:
                    await coord.async_mute_item(item_id)

        hass.data[DOMAIN][f"{DOMAIN}_action_listener"] = hass.bus.async_listen(
            "mobile_app_notification_action",
            handle_notification_action,
        )

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
