"""Binary sensor platform for eGun integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EgunCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up eGun binary sensors from a config entry."""
    coordinator: EgunCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        EgunImminentAuctionAlertBinarySensor(coordinator, entry),
    ])


class EgunImminentAuctionAlertBinarySensor(CoordinatorEntity[EgunCoordinator], BinarySensorEntity):
    """Binary sensor turning ON when an auction is ending within 1 hour under budget."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alarm-light"

    def __init__(self, coordinator: EgunCoordinator, entry: ConfigEntry) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_alerte_fin_imminente"
        self._attr_translation_key = "alerte_fin_imminente"
        self._attr_name = "Alerte fin imminente"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"eGun - {entry.title}",
            "manufacturer": "eGun.de",
            "model": "Veille Carabines Chasse",
            "entry_type": "service",
            "configuration_url": coordinator.base_url,
        }

    @property
    def is_on(self) -> bool:
        """Return True if an auction is ending in less than 60 minutes."""
        items = self.coordinator.data or []
        return any(
            it.is_auction
            and (0 < it.remaining_seconds <= 3600)
            and (it.price <= self.coordinator.max_price)
            for it in items
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return details of auctions ending soon."""
        items = self.coordinator.data or []
        imminent = [
            it.to_display_dict()
            for it in items
            if it.is_auction and (0 < it.remaining_seconds <= 3600) and (it.price <= self.coordinator.max_price)
        ]
        return {
            "imminent_count": len(imminent),
            "imminent_auctions": imminent,
        }
