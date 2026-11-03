"""DataUpdateCoordinator for eGun integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ACTION_MUTE_ITEM,
    ACTION_VIEW_ITEM,
    CONF_CAT,
    CONF_EWB,
    CONF_EXCLUDE_ACCESSORIES,
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
    TURBO_SCAN_INTERVAL,
)
from .scraper import EgunItem, EgunScraper

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


class EgunCoordinator(DataUpdateCoordinator[list[EgunItem]]):
    """Coordinator to manage fetching eGun data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the eGun coordinator."""
        self.entry = entry
        self._session = async_get_clientsession(hass)
        self.scraper = EgunScraper(self._session)

        # Config & options
        self.query: str = entry.data.get(CONF_QUERY, "")
        self.cat: str = entry.data.get(CONF_CAT, DEFAULT_CAT)
        self.shipto: str = entry.data.get(CONF_SHIPTO, DEFAULT_SHIPTO)
        self.ewb: str = entry.data.get(CONF_EWB, DEFAULT_EWB)
        self.exclude_accessories: bool = entry.data.get(CONF_EXCLUDE_ACCESSORIES, True)

        # Dynamic options
        self.max_price: float = float(entry.options.get(CONF_MAX_PRICE, entry.data.get(CONF_MAX_PRICE, DEFAULT_MAX_PRICE)))
        self.scan_interval: int = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        self.notify_targets: list[str] = entry.options.get(CONF_NOTIFY_TARGETS, [DEFAULT_NOTIFY_TARGET])

        # State tracking
        self.seen_item_ids: set[str] = set()
        self.notified_urgent_ids: set[str] = set()
        self.muted_item_ids: set[str] = set()
        self.is_turbo_active: bool = False
        self._first_run_done: bool = False

        # Persistent storage
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}")

        super().__init__(
            hass,
            _LOGGER,
            name=f"eGun {entry.title}",
            update_interval=timedelta(minutes=self.scan_interval),
        )

    @property
    def base_url(self) -> str:
        """Return search URL."""
        return self.scraper.build_search_url(
            query=self.query,
            cat=self.cat,
            max_price=self.max_price,
            shipto=self.shipto,
            ewb=self.ewb,
        )

    async def async_load_stored_data(self) -> None:
        """Load stored cache from disk."""
        try:
            stored = await self._store.async_load()
            if stored and isinstance(stored, dict):
                self.seen_item_ids = set(stored.get("seen_ids", []))
                self.notified_urgent_ids = set(stored.get("notified_urgent_ids", []))
                self.muted_item_ids = set(stored.get("muted_ids", []))
                _LOGGER.debug(
                    "[%s] Loaded %d seen, %d notified, %d muted items",
                    self.entry.title,
                    len(self.seen_item_ids),
                    len(self.notified_urgent_ids),
                    len(self.muted_item_ids),
                )
        except Exception as err:
            _LOGGER.warning("[%s] Failed to load stored eGun cache: %s", self.entry.title, err)

    async def async_save_stored_data(self) -> None:
        """Save cache to disk."""
        try:
            await self._store.async_save({
                "seen_ids": list(self.seen_item_ids),
                "notified_urgent_ids": list(self.notified_urgent_ids),
                "muted_ids": list(self.muted_item_ids),
            })
        except Exception as err:
            _LOGGER.warning("[%s] Failed to save eGun cache: %s", self.entry.title, err)

    async def _async_update_data(self) -> list[EgunItem]:
        """Fetch eGun items and process notifications."""
        if not self._first_run_done:
            await self.async_load_stored_data()

        try:
            items = await self.scraper.async_scrape(
                query=self.query,
                cat=self.cat,
                max_price=self.max_price,
                shipto=self.shipto,
                ewb=self.ewb,
                exclude_accessories=self.exclude_accessories,
            )
        except Exception as err:
            raise UpdateFailed(f"Error scraping eGun: {err}") from err

        # Process notifications & updates
        await self._async_process_items(items)

        # Dynamic Turbo Sprint mode (polling every 3 min if auction ends in < 2h)
        has_imminent_auction = any(
            it.is_auction and (0 < it.remaining_seconds <= 7200) for it in items
        )
        if has_imminent_auction and not self.is_turbo_active:
            self.is_turbo_active = True
            self.update_interval = timedelta(minutes=TURBO_SCAN_INTERVAL)
            _LOGGER.info("[%s] Turbo Sprint activated (polling every %d min)", self.entry.title, TURBO_SCAN_INTERVAL)
        elif not has_imminent_auction and self.is_turbo_active:
            self.is_turbo_active = False
            self.update_interval = timedelta(minutes=self.scan_interval)
            _LOGGER.info("[%s] Turbo Sprint deactivated (polling every %d min)", self.entry.title, self.scan_interval)

        return items

    async def _async_process_items(self, items: list[EgunItem]) -> None:
        """Handle urgent alerts and new item notifications."""
        current_ids = {it.id for it in items}

        for item in items:
            if item.id in self.muted_item_ids:
                continue

            # 1. Urgent notification: auction ends in <= 1 hour (3600s) and still <= budget
            if (
                item.is_auction
                and (0 < item.remaining_seconds <= 3600)
                and (item.price <= self.max_price)
                and (item.id not in self.notified_urgent_ids)
            ):
                await self._async_send_notification(
                    title=f"🚨 eGun : Fin d'enchère imminente (< 1h) !",
                    message=(
                        f"🎯 {item.title}\n"
                        f"💰 Prix actuel : {item.price_str} ({item.bids_count} offres)\n"
                        f"⏳ Fin dans : {item.remaining_time_str}\n"
                        f"👤 Vendeur : {item.seller} ({item.seller_type})"
                    ),
                    item=item,
                    is_urgent=True,
                )
                self.notified_urgent_ids.add(item.id)

            # 2. New item notification
            if self._first_run_done and (item.id not in self.seen_item_ids):
                await self._async_send_notification(
                    title=f"🎯 eGun : Nouvelle annonce ({self.entry.title})",
                    message=(
                        f"🔫 {item.title}\n"
                        f"💶 Prix : {item.price_str} ({'Enchère' if item.is_auction else 'Achat immédiat'})\n"
                        f"🏷️ Type : {item.action_type.capitalize()} | {item.condition.capitalize()}\n"
                        f"👤 Vendeur : {item.seller} ({item.seller_type})"
                    ),
                    item=item,
                    is_urgent=False,
                )

            self.seen_item_ids.add(item.id)

        # Clean expired urgent notification IDs
        self.notified_urgent_ids.intersection_update(current_ids)

        if not self._first_run_done:
            self._first_run_done = True

        await self.async_save_stored_data()

    async def _async_send_notification(
        self, title: str, message: str, item: EgunItem, is_urgent: bool = False
    ) -> None:
        """Send notification to configured notify services."""
        if not self.notify_targets:
            return

        actions = [
            {"action": "URI", "title": "Voir sur eGun 🎯", "uri": item.url},
            {"action": f"{ACTION_MUTE_ITEM}_{item.id}", "title": "Ignorer 🔕"},
        ]

        data: dict[str, Any] = {
            "title": title,
            "message": message,
            "data": {
                "tag": f"egun_{item.id}",
                "url": item.url,
                "clickAction": item.url,
                "actions": actions,
                "priority": "high" if is_urgent else "normal",
                "ttl": 0 if is_urgent else 86400,
            },
        }
        if item.image_url:
            data["data"]["image"] = item.image_url

        for target in self.notify_targets:
            service_name = target.replace("notify.", "")
            try:
                await self.hass.services.async_call("notify", service_name, data)
                _LOGGER.info("[%s] Notification sent to %s for item %s", self.entry.title, target, item.id)
            except Exception as err:
                _LOGGER.error("[%s] Failed to send notification to %s: %s", self.entry.title, target, err)

    async def async_set_max_price(self, new_max_price: float) -> None:
        """Update max_price budget option."""
        self.max_price = new_max_price
        new_options = dict(self.entry.options)
        new_options[CONF_MAX_PRICE] = new_max_price
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)

    async def async_mute_item(self, item_id: str) -> None:
        """Mute an item from future alerts."""
        self.muted_item_ids.add(str(item_id))
        await self.async_save_stored_data()

    async def async_unmute_item(self, item_id: str) -> None:
        """Unmute an item."""
        self.muted_item_ids.discard(str(item_id))
        await self.async_save_stored_data()

    async def async_reset_cache(self) -> None:
        """Clear cache of seen and notified items."""
        self.seen_item_ids.clear()
        self.notified_urgent_ids.clear()
        self.muted_item_ids.clear()
        await self.async_save_stored_data()
        await self.async_request_refresh()
