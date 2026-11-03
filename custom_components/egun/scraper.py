"""Scraper engine for eGun.de."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any
import urllib.parse

import aiohttp
from bs4 import BeautifulSoup

from .const import BASE_URL, DEFAULT_CAT, DEFAULT_EWB, DEFAULT_SHIPTO, SEARCH_URL

_LOGGER = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def clean_price(text: str | None) -> float | None:
    """Clean and parse a price string to float."""
    if not text:
        return None
    cleaned = text.replace("&euro;", "").replace("€", "").replace("\xa0", " ").strip()
    cleaned = re.sub(r"[^\d,.]", "", cleaned)
    if not cleaned:
        return None
    # German format: 1.250,00 -> 1250.00
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def format_remaining_time(seconds: int) -> str:
    """Format remaining seconds into human readable French string."""
    if seconds <= 0:
        return "Terminé"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    if days > 0:
        return f"{days}j {hours:02d}h"
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


@dataclass
class EgunItem:
    """Represents a single item/auction listed on eGun."""

    id: str
    title: str
    url: str
    image_url: str | None
    price: float
    price_str: str
    price_label: str
    is_auction: bool
    is_buy_now: bool
    bids_count: int
    ends_timestamp: int
    remaining_seconds: int
    remaining_time_str: str
    seller: str
    seller_type: str
    condition: str
    is_accessory: bool
    action_type: str
    brand: str
    has_optic: bool
    optic_name: str | None
    is_threaded: bool
    has_silencer: bool
    is_stainless: bool
    is_left_handed: bool
    first_seen: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert item to full dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "image_url": self.image_url,
            "price": self.price,
            "price_str": self.price_str,
            "price_label": self.price_label,
            "is_auction": self.is_auction,
            "is_buy_now": self.is_buy_now,
            "bids_count": self.bids_count,
            "ends_timestamp": self.ends_timestamp,
            "remaining_seconds": self.remaining_seconds,
            "remaining_time": self.remaining_time_str,
            "seller": self.seller,
            "seller_type": self.seller_type,
            "condition": self.condition,
            "is_accessory": self.is_accessory,
            "action_type": self.action_type,
            "brand": self.brand,
            "has_optic": self.has_optic,
            "optic_name": self.optic_name,
            "is_threaded": self.is_threaded,
            "has_silencer": self.has_silencer,
            "is_stainless": self.is_stainless,
            "is_left_handed": self.is_left_handed,
            "first_seen": self.first_seen,
        }

    def to_display_dict(self) -> dict[str, Any]:
        """Compact dictionary optimized for Lovelace flex-table-card and under 16KB limit."""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "image_url": self.image_url,
            "price": self.price,
            "price_str": self.price_str,
            "is_auction": self.is_auction,
            "remaining_time": self.remaining_time_str,
            "remaining_seconds": self.remaining_seconds,
            "bids_count": self.bids_count,
            "brand": self.brand,
            "condition": self.condition,
            "seller_type": self.seller_type,
            "action_type": self.action_type,
            "has_optic": self.has_optic,
            "optic_name": self.optic_name,
            "is_threaded": self.is_threaded,
            "has_silencer": self.has_silencer,
            "is_stainless": self.is_stainless,
            "is_left_handed": self.is_left_handed,
        }


class EgunScraper:
    """Scraper for eGun.de search pages."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize scraper."""
        self._session = session

    def build_search_url(
        self,
        query: str,
        cat: str = DEFAULT_CAT,
        max_price: float = 600.0,
        shipto: str = DEFAULT_SHIPTO,
        ewb: str = DEFAULT_EWB,
        page: int = 1,
    ) -> str:
        """Build exact eGun search URL."""
        params = {
            "query": query,
            "cat": cat,
            "wheremode": "and",
            "plusdescr": "1",
            "nick": "",
            "country": "0",
            "minprice": "",
            "maxprice": int(max_price) if max_price.is_integer() else max_price,
            "zip": "",
            "radius": "0",
            "type": "0",
            "cond": "",
            "seller": "",
            "status": "",
            "ewb": ewb,
            "shipto": shipto,
            "order": "ends",
            "asdes": "asc",
            "page": page,
            "per": "50",
        }
        return f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"

    async def async_scrape(
        self,
        query: str,
        cat: str = DEFAULT_CAT,
        max_price: float = 600.0,
        shipto: str = DEFAULT_SHIPTO,
        ewb: str = DEFAULT_EWB,
        exclude_accessories: bool = True,
    ) -> list[EgunItem]:
        """Fetch and parse search results from eGun."""
        url = self.build_search_url(
            query=query, cat=cat, max_price=max_price, shipto=shipto, ewb=ewb
        )
        _LOGGER.debug("Scraping eGun URL: %s", url)

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,de;q=0.7",
        }

        if self._session is None:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status != 200:
                        _LOGGER.error("eGun returned HTTP %s for URL: %s", resp.status, url)
                        return []
                    html = await resp.text()
        else:
            async with self._session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    _LOGGER.error("eGun returned HTTP %s for URL: %s", resp.status, url)
                    return []
                html = await resp.text()

        return self.parse_html(html, max_price=max_price, exclude_accessories=exclude_accessories)

    def parse_html(
        self, html: str, max_price: float = 600.0, exclude_accessories: bool = True
    ) -> list[EgunItem]:
        """Parse eGun HTML and return list of EgunItem."""
        soup = BeautifulSoup(html, "html.parser")
        items: list[EgunItem] = []
        now = int(time.time())

        # Select all item listing <li>
        for li in soup.select("ul.auction-list > li[data-auction-id]"):
            try:
                aid = li.get("data-auction-id")
                if not aid:
                    continue

                title_el = li.select_one(".list-item__title-text")
                title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    continue

                link_el = li.select_one("a.list-item__link")
                href = link_el.get("href", "") if link_el else ""
                item_url = f"{BASE_URL}{href}" if href.startswith("/") else (href or f"{BASE_URL}/item/{aid}")

                img_el = li.select_one(".list-item__thumb img")
                img_src = img_el.get("src", "") if img_el else ""
                image_url = f"{BASE_URL}{img_src}" if img_src.startswith("/") else img_src

                seller_el = li.select_one(".list-item__seller")
                seller = seller_el.get_text(strip=True) if seller_el else "Inconnu"

                business_badge = li.select_one(".badge--business")
                seller_type = (
                    "professionnel"
                    if (business_badge and "gewerblich" in business_badge.get_text().lower())
                    else "particulier"
                )

                cond_badge = li.select_one(".badge--condition")
                cond_text = cond_badge.get_text().lower() if cond_badge else ""
                condition = "neuf" if ("neu" in cond_text and "neuwertig" not in cond_text) else "occasion"

                price_label_el = li.select_one(".list-item__price-label")
                price_label = price_label_el.get_text(strip=True) if price_label_el else ""

                price_el = li.select_one(".list-item__price")
                price_raw = price_el.get_text(strip=True) if price_el else ""
                price = clean_price(price_raw)
                if price is None:
                    continue

                # Check if exceeds max_price
                if price > max_price:
                    continue

                price_str = f"{price:.2f} €"

                bids_el = li.select_one(".list-item__bids") or li.select_one(".list-item__price-sub")
                bids_text = bids_el.get_text(strip=True) if bids_el else ""
                bids_m = re.search(r"(\d+)\s*Gebot", bids_text)
                bids_count = int(bids_m.group(1)) if bids_m else 0

                is_auction = (
                    "gebot" in price_label.lower()
                    or "startpreis" in price_label.lower()
                    or bids_count > 0
                )
                is_buy_now = "sofortkauf" in price_label.lower()

                ends_el = li.select_one(".list-item__ends")
                ends_ts = int(ends_el.get("data-ends", 0)) if (ends_el and ends_el.get("data-ends")) else 0
                remaining_seconds = max(0, ends_ts - now) if ends_ts > 0 else 0
                remaining_time_str = format_remaining_time(remaining_seconds)

                # Metadata enrichment
                t_lower = title.lower()

                # Accessory detection
                is_acc = any(
                    w in t_lower
                    for w in [
                        "magazin", "schaft", "verschlusskopf", "pufferpatrone", "dekopatrone",
                        "montage", "lauf ", "waffenpflege", "reinigung", "putzzeug", "koffer",
                        "futteral", "riemen", "patronenbox", "holster", "schalldämpfer "
                    ]
                ) and not any(
                    w in t_lower
                    for w in [
                        "repetierbüchse", "büchse", "repetierer", "gewehr", "stutzen", "karabiner"
                    ]
                )
                if any(w in t_lower for w in ["waffenpflege", "reinigung", "pufferpatrone", "dekopatrone", "magazinboden"]):
                    is_acc = True

                if exclude_accessories and is_acc:
                    continue

                # Straight-pull vs bolt-action
                is_linear = any(
                    w in t_lower
                    for w in [
                        "geradezug", "linear", "helix", "maral", "brx1", "r93", "r8",
                        "impulse", "sr30", "sr 30", "steel action", "strasser", "rols"
                    ]
                )
                action_type = "lineaire" if is_linear else "verrou"

                # Brand detection
                brand = "Autre"
                known_brands = [
                    ("Heym", ["heym", "sr20", "sr21", "sr30"]),
                    ("Merkel", ["merkel", "rx helix", "helix", "kr1"]),
                    ("Blaser", ["blaser", "r93", "r8"]),
                    ("Sauer", ["sauer", "s100", "s101", "s202", "s404", "s80", "s90"]),
                    ("Browning", ["browning", "x-bolt", "a-bolt", "maral"]),
                    ("Tikka", ["tikka", "t3", "t3x", "m55", "m65"]),
                    ("Sako", ["sako", "s20", "sako 85", "sako 75", "finnbear"]),
                    ("Beretta", ["beretta", "brx1"]),
                    ("CZ", ["cz ", "cz5", "cz6", "ceska", "brünner", "brno"]),
                    ("Mauser", ["mauser", "m12", "m18", "m98", "system 98"]),
                    ("Remington", ["remington", "model 700", "mod. 700", "783"]),
                    ("Winchester", ["winchester", "xpr", "model 70"]),
                    ("Steyr", ["steyr", "mannlicher", "steyr-mannlicher"]),
                    ("Ruger", ["ruger", "american rifle", "m77"]),
                    ("Bergara", ["bergara", "b14"]),
                    ("Haenel", ["haenel", "jaeger 10"]),
                    ("Zastava", ["zastava", "m70", "m98"]),
                    ("Krico", ["krico"]),
                    ("Voere", ["voere"]),
                    ("BSA", ["bsa"]),
                    ("Savage", ["savage", "axis", "110", "impulse"]),
                    ("Renato Baldi", ["baldi", "renato baldi"]),
                ]
                for b_name, triggers in known_brands:
                    if any(tr in t_lower for tr in triggers):
                        brand = b_name
                        break

                # Optic detection
                has_optic = False
                optic_name = None
                optic_keywords = [
                    ("Zeiss", ["zeiss"]),
                    ("Swarovski", ["swarovski"]),
                    ("Schmidt & Bender", ["schmidt & bender", "schmidt und bender", "s&b"]),
                    ("Kahles", ["kahles"]),
                    ("Meopta", ["meopta"]),
                    ("Steiner", ["steiner"]),
                    ("Kaps", ["kaps"]),
                    ("Leupold", ["leupold"]),
                    ("Minox", ["minox"]),
                    ("Vortex", ["vortex"]),
                    ("Burris", ["burris"]),
                    ("Docter", ["docter"]),
                    ("Aimpoint", ["aimpoint"]),
                    ("Nikko Stirling", ["nikko", "stirling"]),
                    ("Sutter", ["sutter"]),
                    ("Optique / ZF", ["zf", "zielfernrohr", "optik", "rotpunkt", "point rouge"]),
                ]
                for opt_name, triggers in optic_keywords:
                    if any(tr in t_lower for tr in triggers):
                        has_optic = True
                        optic_name = opt_name
                        break

                # Thread / silencer
                is_threaded = any(
                    w in t_lower
                    for w in ["gewinde", "mündungsgewinde", "m14", "m15", "m18", "14x1", "15x1", "fileté", "filetage"]
                )
                has_silencer = any(w in t_lower for w in ["schalldämpfer", "sd", "silencieux", "modérateur"])
                if has_silencer:
                    is_threaded = True

                # Stainless / Left-handed
                is_stainless = any(w in t_lower for w in ["edelstahl", "stainless", "inox"])
                is_left_handed = any(w in t_lower for w in ["links", "linkshänder", "linkssystem", "gauch"])

                items.append(
                    EgunItem(
                        id=aid,
                        title=title,
                        url=item_url,
                        image_url=image_url,
                        price=price,
                        price_str=price_str,
                        price_label=price_label,
                        is_auction=is_auction,
                        is_buy_now=is_buy_now,
                        bids_count=bids_count,
                        ends_timestamp=ends_ts,
                        remaining_seconds=remaining_seconds,
                        remaining_time_str=remaining_time_str,
                        seller=seller,
                        seller_type=seller_type,
                        condition=condition,
                        is_accessory=is_acc,
                        action_type=action_type,
                        brand=brand,
                        has_optic=has_optic,
                        optic_name=optic_name,
                        is_threaded=is_threaded,
                        has_silencer=has_silencer,
                        is_stainless=is_stainless,
                        is_left_handed=is_left_handed,
                    )
                )

            except Exception as item_err:
                _LOGGER.debug("Failed to parse eGun item element: %s", item_err)
                continue

        return items
