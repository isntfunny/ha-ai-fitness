"""Constants for the AI Fitness integration."""

from __future__ import annotations

DOMAIN = "ai_fitness"

ATTRIBUTION = "Daten von ai-fitness.de"
MANUFACTURER = "AI Fitness"

CONF_STUDIO_ID = "studio_id"
CONF_STUDIO_NAME = "studio_name"
CONF_QUERY = "query"
CONF_SCAN_INTERVAL = "scan_interval"

# An entry is either an anonymous studio (utilization) or a member account
# (check-ins). Check-ins are account-wide, so they must not be duplicated per
# studio — hence two entry types instead of one combined entry.
CONF_ENTRY_TYPE = "entry_type"
ENTRY_TYPE_STUDIO = "studio"
ENTRY_TYPE_ACCOUNT = "account"

CONF_REFRESH_TOKEN = "refresh_token"  # noqa: S105 - config key, not a secret

DEFAULT_SCAN_INTERVAL = 5  # minutes
MIN_SCAN_INTERVAL = 1
MAX_SCAN_INTERVAL = 120

# Check-ins change a couple of times per day at most.
DEFAULT_ACCOUNT_SCAN_INTERVAL = 30  # minutes

# How many studios to offer in the "nearby" picker.
NEARBY_LIMIT = 15
# Upper bound for the search result picker.
SEARCH_LIMIT = 25

LEVEL_LOW = "LOW"
LEVEL_MEDIUM = "MEDIUM"
LEVEL_HIGH = "HIGH"
LEVELS = [LEVEL_LOW, LEVEL_MEDIUM, LEVEL_HIGH]
