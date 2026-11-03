"""Sensor platform for eGun integration."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EgunCoordinator
from .scraper import EgunItem

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up eGun sensors from a config entry."""
    coordinator: EgunCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        EgunTotalItemsSensor(coordinator, entry),
        EgunActiveAuctionsSensor(coordinator, entry),
        EgunNextAuctionEndSensor(coordinator, entry),
        EgunLatestItemSensor(coordinator, entry),
        EgunLowestPriceSensor(coordinator, entry),
        EgunEquippedItemsSensor(coordinator, entry),
    ]

    async_add_entities(entities)


class EgunBaseSensor(CoordinatorEntity[EgunCoordinator], SensorEntity):
    """Base class for eGun sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EgunCoordinator, entry: ConfigEntry, key: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = key
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"eGun - {entry.title}",
            "manufacturer": "eGun.de",
            "model": "Veille Carabines Chasse",
            "entry_type": "service",
            "configuration_url": coordinator.base_url,
        }


class EgunTotalItemsSensor(EgunBaseSensor):
    """Sensor reporting total number of items found under budget."""

    _attr_icon = "mdi:rifle"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "annonces"

    def __init__(self, coordinator: EgunCoordinator, entry: ConfigEntry) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, entry, "total_annonces")
        self._attr_translation_key = "total_annonces"
        self._attr_name = "Total annonces"

    @property
    def native_value(self) -> int:
        """Return total items count."""
        return len(self.coordinator.data or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return compact attributes for Lovelace flex-table-card."""
        items = self.coordinator.data or []
        equipped = [it for it in items if it.has_optic or it.is_threaded or it.has_silencer]
        linear = [it for it in items if it.action_type == "lineaire"]
        bolt = [it for it in items if it.action_type == "verrou"]
        cheapest_dict = min(items, key=lambda x: x.price).to_display_dict() if items else {}

        return {
            "max_price": self.coordinator.max_price,
            "query": self.coordinator.query,
            "cat": self.coordinator.cat,
            "shipto": self.coordinator.shipto,
            "muted_items_count": len(self.coordinator.muted_item_ids),
            "is_turbo_active": self.coordinator.is_turbo_active,
            "url": self.coordinator.base_url,
            "items": [item.to_display_dict() for item in items[:18]],
            "cheapest_item": cheapest_dict,
            "equipped_count": len(equipped),
            "linear_count": len(linear),
            "bolt_count": len(bolt),
        }


class EgunActiveAuctionsSensor(EgunBaseSensor):
    """Sensor reporting count of active auctions."""

    _attr_icon = "mdi:gavel"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "enchères"

    def __init__(self, coordinator: EgunCoordinator, entry: ConfigEntry) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, entry, "encheres_actives")
        self._attr_translation_key = "encheres_actives"
        self._attr_name = "Enchères actives"

    @property
    def native_value(self) -> int:
        """Return number of active auctions."""
        items = self.coordinator.data or []
        return sum(1 for it in items if it.is_auction)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return compact auctions list."""
        items = self.coordinator.data or []
        auctions = [it for it in items if it.is_auction]
        return {
            "auctions_count": len(auctions),
            "auctions": [a.to_display_dict() for a in auctions[:10]],
        }


class EgunNextAuctionEndSensor(EgunBaseSensor):
    """Sensor indicating the nearest auction ending timestamp."""

    _attr_icon = "mdi:clock-fast"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: EgunCoordinator, entry: ConfigEntry) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, entry, "prochaine_fin_d_enchere")
        self._attr_translation_key = "prochaine_fin_d_enchere"
        self._attr_name = "Prochaine fin d'enchère"

    def _get_next_auction(self) -> EgunItem | None:
        """Find auction ending earliest."""
        items = self.coordinator.data or []
        auctions = [it for it in items if it.is_auction and it.remaining_seconds > 0]
        if not auctions:
            return None
        return min(auctions, key=lambda a: a.remaining_seconds)

    @property
    def native_value(self) -> datetime | None:
        """Return timestamp of next ending auction in UTC."""
        next_auc = self._get_next_auction()
        if not next_auc or next_auc.ends_timestamp <= 0:
            return None
        return datetime.fromtimestamp(next_auc.ends_timestamp, tz=timezone.utc)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return details of next auction."""
        next_auc = self._get_next_auction()
        if not next_auc:
            return {}
        return {
            "item_id": next_auc.id,
            "title": next_auc.title,
            "url": next_auc.url,
            "price": next_auc.price,
            "price_str": next_auc.price_str,
            "bids_count": next_auc.bids_count,
            "remaining_seconds": next_auc.remaining_seconds,
            "remaining_time": next_auc.remaining_time_str,
        }


class EgunLatestItemSensor(EgunBaseSensor):
    """Sensor displaying the most recently listed item."""

    _attr_icon = "mdi:new-box"

    def __init__(self, coordinator: EgunCoordinator, entry: ConfigEntry) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, entry, "derniere_annonce")
        self._attr_translation_key = "derniere_annonce"
        self._attr_name = "Dernière annonce"

    @property
    def native_value(self) -> str:
        """Return title of latest item."""
        items = self.coordinator.data or []
        if not items:
            return "Aucune annonce"
        return items[0].title[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return details of latest item."""
        items = self.coordinator.data or []
        if not items:
            return {}
        latest = items[0]
        return {
            "id": latest.id,
            "title": latest.title,
            "url": latest.url,
            "price": latest.price,
            "price_str": latest.price_str,
            "is_auction": latest.is_auction,
            "condition": latest.condition,
            "seller": latest.seller,
        }


class EgunLowestPriceSensor(EgunBaseSensor):
    """Sensor tracking the lowest priced rifle."""

    _attr_icon = "mdi:tag-outline"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "EUR"

    def __init__(self, coordinator: EgunCoordinator, entry: ConfigEntry) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, entry, "prix_minimum")
        self._attr_translation_key = "prix_minimum"
        self._attr_name = "Prix minimum"

    @property
    def native_value(self) -> float | None:
        """Return the lowest price found."""
        items = self.coordinator.data or []
        if not items:
            return None
        return min(it.price for it in items)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return cheapest item details."""
        items = self.coordinator.data or []
        if not items:
            return {}
        cheapest = min(items, key=lambda it: it.price)
        return {
            "item_id": cheapest.id,
            "title": cheapest.title,
            "url": cheapest.url,
            "price_str": cheapest.price_str,
            "is_auction": cheapest.is_auction,
            "action_type": cheapest.action_type,
        }


class EgunEquippedItemsSensor(EgunBaseSensor):
    """Sensor reporting rifles equipped with optics, threading, or silencers."""

    _attr_icon = "mdi:telescope"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "packs"

    def __init__(self, coordinator: EgunCoordinator, entry: ConfigEntry) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, entry, "carabines_equipees")
        self._attr_translation_key = "carabines_equipees"
        self._attr_name = "Carabines équipées"

    @property
    def native_value(self) -> int:
        """Return count of equipped rifles."""
        items = self.coordinator.data or []
        return sum(1 for it in items if it.has_optic or it.is_threaded or it.has_silencer)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return sample of equipped rifles."""
        items = self.coordinator.data or []
        equipped = [it.to_display_dict() for it in items if it.has_optic or it.is_threaded or it.has_silencer]
        return {
            "equipped_count": len(equipped),
            "equipped_items": equipped[:12],
        }
