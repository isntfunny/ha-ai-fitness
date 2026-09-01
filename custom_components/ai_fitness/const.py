"""Constants for the AI Fitness integration."""

from __future__ import annotations

DOMAIN = "ai_fitness"

ATTRIBUTION = "Daten von ai-fitness.de"
MANUFACTURER = "AI Fitness"

CONF_STUDIO_ID = "studio_id"
CONF_STUDIO_NAME = "studio_name"
CONF_QUERY = "query"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 5  # minutes
MIN_SCAN_INTERVAL = 1
MAX_SCAN_INTERVAL = 120

# How many studios to offer in the "nearby" picker.
NEARBY_LIMIT = 15
# Upper bound for the search result picker.
SEARCH_LIMIT = 25

LEVEL_LOW = "LOW"
LEVEL_MEDIUM = "MEDIUM"
LEVEL_HIGH = "HIGH"
LEVELS = [LEVEL_LOW, LEVEL_MEDIUM, LEVEL_HIGH]
