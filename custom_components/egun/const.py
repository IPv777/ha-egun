"""Constants for the eGun integration."""

DOMAIN = "egun"
DEFAULT_NAME = "eGun"

# Configuration options
CONF_FEED_PRESET = "feed_preset"
CONF_QUERY = "query"
CONF_CAT = "cat"
CONF_MAX_PRICE = "max_price"
CONF_SHIPTO = "shipto"
CONF_EWB = "ewb"
CONF_NOTIFY_TARGETS = "notify_targets"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_CALIBER = "caliber"
CONF_EXCLUDE_ACCESSORIES = "exclude_accessories"

# Defaults
DEFAULT_MAX_PRICE = 600.0
DEFAULT_SCAN_INTERVAL = 15  # minutes
TURBO_SCAN_INTERVAL = 3     # minutes when an auction ends in < 2h
DEFAULT_SHIPTO = "8"        # France
DEFAULT_CAT = "72"          # Repetierbüchsen (bolt-action & straight-pull rifles)
DEFAULT_EWB = "x"           # egal (all with/without EWB)
DEFAULT_NOTIFY_TARGET = "notify.mobile_app_thinkphone_by_motorola"

# URLs
BASE_URL = "https://www.egun.de"
SEARCH_URL = "https://www.egun.de/search"

# Presets
PRESET_30_06 = "carabines_30_06"
PRESET_308 = "carabines_308"
PRESET_CUSTOM = "custom"

PRESETS = {
    PRESET_30_06: {
        "name": "Carabines 30-06",
        "query": "30 06",
        "cat": "72",
        "shipto": "8",
        "caliber": "30-06",
    },
    PRESET_308: {
        "name": "Carabines 308",
        "query": "308",
        "cat": "72",
        "shipto": "8",
        "caliber": "308",
    },
}

# Actionable notification actions
ACTION_VIEW_ITEM = "EGUN_VIEW_ITEM"
ACTION_MUTE_ITEM = "EGUN_MUTE_ITEM"
