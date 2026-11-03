"""Config flow and Options flow for eGun integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_CAT,
    CONF_EWB,
    CONF_EXCLUDE_ACCESSORIES,
    CONF_FEED_PRESET,
    CONF_MAX_PRICE,
    CONF_NOTIFY_TARGETS,
    CONF_QUERY,
    CONF_SCAN_INTERVAL,
    CONF_SHIPTO,
    DEFAULT_CAT,
    DEFAULT_EWB,
    DEFAULT_MAX_PRICE,
    DEFAULT_NOTIFY_TARGET,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SHIPTO,
    DOMAIN,
    PRESET_308,
    PRESET_30_06,
    PRESET_CUSTOM,
    PRESETS,
)

_LOGGER = logging.getLogger(__name__)


class EgunConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for eGun."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._preset_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            preset = user_input.get(CONF_FEED_PRESET, PRESET_30_06)

            if preset == PRESET_CUSTOM:
                self._preset_data = user_input
                return await self.async_step_custom()

            preset_info = PRESETS.get(preset, PRESETS[PRESET_30_06])
            title = f"eGun - {preset_info['name']}"
            unique_id = f"egun_{preset_info['query']}_{preset_info['cat']}_{preset_info['shipto']}"

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            notify_target = user_input.get("notify_target", DEFAULT_NOTIFY_TARGET)

            return self.async_create_entry(
                title=title,
                data={
                    CONF_QUERY: preset_info["query"],
                    CONF_CAT: preset_info["cat"],
                    CONF_SHIPTO: preset_info["shipto"],
                    CONF_EWB: DEFAULT_EWB,
                    CONF_MAX_PRICE: user_input.get(CONF_MAX_PRICE, DEFAULT_MAX_PRICE),
                    CONF_EXCLUDE_ACCESSORIES: user_input.get(CONF_EXCLUDE_ACCESSORIES, True),
                },
                options={
                    CONF_MAX_PRICE: user_input.get(CONF_MAX_PRICE, DEFAULT_MAX_PRICE),
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    CONF_NOTIFY_TARGETS: [notify_target] if notify_target else [DEFAULT_NOTIFY_TARGET],
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_FEED_PRESET, default=PRESET_30_06): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": PRESET_30_06, "label": "Carabines 30-06 (Calibre 30-06)"},
                            {"value": PRESET_308, "label": "Carabines 308 (Calibre .308 Win)"},
                            {"value": PRESET_CUSTOM, "label": "Recherche personnalisée"},
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_MAX_PRICE, default=DEFAULT_MAX_PRICE): vol.Coerce(float),
                vol.Optional("notify_target", default=DEFAULT_NOTIFY_TARGET): str,
                vol.Optional(CONF_EXCLUDE_ACCESSORIES, default=True): bool,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_custom(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle custom search parameter configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            query = user_input[CONF_QUERY]
            cat = user_input.get(CONF_CAT, DEFAULT_CAT)
            shipto = user_input.get(CONF_SHIPTO, DEFAULT_SHIPTO)
            unique_id = f"egun_{query}_{cat}_{shipto}"

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            title = f"eGun - {query}"
            notify_target = self._preset_data.get("notify_target", DEFAULT_NOTIFY_TARGET)
            max_price = self._preset_data.get(CONF_MAX_PRICE, DEFAULT_MAX_PRICE)

            return self.async_create_entry(
                title=title,
                data={
                    CONF_QUERY: query,
                    CONF_CAT: cat,
                    CONF_SHIPTO: shipto,
                    CONF_EWB: user_input.get(CONF_EWB, DEFAULT_EWB),
                    CONF_MAX_PRICE: max_price,
                    CONF_EXCLUDE_ACCESSORIES: user_input.get(CONF_EXCLUDE_ACCESSORIES, True),
                },
                options={
                    CONF_MAX_PRICE: max_price,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    CONF_NOTIFY_TARGETS: [notify_target] if notify_target else [DEFAULT_NOTIFY_TARGET],
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_QUERY): str,
                vol.Optional(CONF_CAT, default=DEFAULT_CAT): str,
                vol.Optional(CONF_SHIPTO, default=DEFAULT_SHIPTO): str,
                vol.Optional(CONF_EWB, default=DEFAULT_EWB): str,
                vol.Optional(CONF_EXCLUDE_ACCESSORIES, default=True): bool,
            }
        )

        return self.async_show_form(step_id="custom", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return EgunOptionsFlowHandler(config_entry)


class EgunOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for eGun."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            raw_targets = user_input.get(CONF_NOTIFY_TARGETS, "")
            if isinstance(raw_targets, str):
                targets = [t.strip() for t in raw_targets.split(",") if t.strip()]
            elif isinstance(raw_targets, list):
                targets = raw_targets
            else:
                targets = [DEFAULT_NOTIFY_TARGET]

            return self.async_create_entry(
                title="",
                data={
                    CONF_MAX_PRICE: float(user_input.get(CONF_MAX_PRICE, DEFAULT_MAX_PRICE)),
                    CONF_SCAN_INTERVAL: int(user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
                    CONF_NOTIFY_TARGETS: targets,
                    CONF_EXCLUDE_ACCESSORIES: user_input.get(CONF_EXCLUDE_ACCESSORIES, True),
                },
            )

        current_max = self._config_entry.options.get(
            CONF_MAX_PRICE,
            self._config_entry.data.get(CONF_MAX_PRICE, DEFAULT_MAX_PRICE),
        )
        current_interval = self._config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        current_targets = self._config_entry.options.get(
            CONF_NOTIFY_TARGETS, [DEFAULT_NOTIFY_TARGET]
        )
        current_exclude = self._config_entry.options.get(
            CONF_EXCLUDE_ACCESSORIES,
            self._config_entry.data.get(CONF_EXCLUDE_ACCESSORIES, True),
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_MAX_PRICE, default=float(current_max)): vol.Coerce(float),
                vol.Required(CONF_SCAN_INTERVAL, default=int(current_interval)): vol.All(
                    vol.Coerce(int), vol.Range(min=3, max=120)
                ),
                vol.Optional(CONF_NOTIFY_TARGETS, default=",".join(current_targets)): str,
                vol.Optional(CONF_EXCLUDE_ACCESSORIES, default=bool(current_exclude)): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
