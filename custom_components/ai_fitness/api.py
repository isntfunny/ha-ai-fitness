"""
Thin async client for the public AI Fitness (Magicline Connect) endpoints.

Both endpoints are public — no authentication, no API key.

Important: the upstream reverse proxy answers ``406 Not Acceptable`` when the
request carries ``Accept: application/json``. Sending ``Accept: */*`` works, so
the headers below must not be "helpfully" tightened.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://www.ai-fitness.de"
STUDIOS_PATH = "/connect/v2/studio"
UTILIZATION_PATH = "/connect/v1/studio/{studio_id}/utilization"

REQUEST_HEADERS = {
    # A browser-ish UA keeps the CDN happy.
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    # Must NOT be application/json — see module docstring.
    "Accept": "*/*",
}

TIMEOUT = aiohttp.ClientTimeout(total=30)


class AiFitnessError(Exception):
    """Base error for the AI Fitness API."""


class AiFitnessConnectionError(AiFitnessError):
    """Raised when the API cannot be reached."""


class AiFitnessStudioNotFoundError(AiFitnessError):
    """Raised when a studio id yields no utilization data."""


@dataclass(slots=True)
class Studio:
    """A single AI Fitness studio."""

    id: str
    name: str
    street: str | None = None
    zip_code: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    @property
    def address(self) -> str:
        """Return a one-line postal address."""
        parts = [p for p in (self.street, self._city_line) if p]
        return ", ".join(parts)

    @property
    def _city_line(self) -> str | None:
        parts = [p for p in (self.zip_code, self.city) if p]
        return " ".join(parts) if parts else None

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Studio | None:
        """Build a Studio from an API payload entry, or None if unusable."""
        studio_id = raw.get("id")
        name = raw.get("studioName")
        if studio_id is None or not name:
            return None

        address = raw.get("address") or {}
        street = address.get("street")
        house_number = address.get("houseNumber")
        if street and house_number:
            street = f"{street} {house_number}"

        return cls(
            id=str(studio_id),
            name=str(name).strip(),
            street=street,
            zip_code=address.get("zipCode"),
            city=address.get("city"),
            latitude=address.get("latitude"),
            longitude=address.get("longitude"),
        )


@dataclass(slots=True)
class Utilization:
    """Parsed utilization payload for one studio."""

    percentage: int | None = None
    level: str | None = None
    slot_start: str | None = None
    slot_end: str | None = None
    is_open: bool = False
    day_start: str | None = None
    day_end: str | None = None
    peak_percentage: int | None = None
    peak_start: str | None = None
    items: list[dict[str, Any]] = field(default_factory=list)
    elapsed_items: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Utilization:
        """Build a Utilization from the raw endpoint payload."""
        items = raw.get("items") or []
        parsed = cls(
            day_start=raw.get("startTime"),
            day_end=raw.get("endTime"),
            items=items,
        )

        current_index = next(
            (n for n, i in enumerate(items) if i.get("isCurrent")), None
        )
        if current_index is not None:
            current = items[current_index]
            parsed.percentage = current.get("percentage")
            parsed.level = current.get("level")
            parsed.slot_start = current.get("startTime")
            parsed.slot_end = current.get("endTime")
            parsed.is_open = True

        # Slots after the current one are always reported as 0 — the endpoint
        # serves measured values for the day so far, not a forecast. Limiting
        # the peak to elapsed slots keeps those placeholder zeros out of it.
        elapsed = items[: current_index + 1] if current_index is not None else items
        parsed.elapsed_items = elapsed

        peak = max(
            (i for i in elapsed if isinstance(i.get("percentage"), int)),
            key=lambda i: i["percentage"],
            default=None,
        )
        if peak is not None:
            parsed.peak_percentage = peak.get("percentage")
            parsed.peak_start = peak.get("startTime")

        return parsed


async def _get_json(session: aiohttp.ClientSession, url: str) -> Any:
    """GET a URL and return the decoded JSON body."""
    try:
        async with session.get(
            url, headers=REQUEST_HEADERS, timeout=TIMEOUT
        ) as response:
            response.raise_for_status()
            # The endpoint serves JSON but does not always set the JSON
            # content type, so skip aiohttp's content-type check.
            return await response.json(content_type=None)
    except aiohttp.ClientError as err:
        raise AiFitnessConnectionError(f"Request to {url} failed: {err}") from err
    except (TimeoutError, ValueError) as err:
        raise AiFitnessConnectionError(f"Bad response from {url}: {err}") from err


async def async_get_studios(session: aiohttp.ClientSession) -> list[Studio]:
    """Fetch the full list of studios (single request, no auth)."""
    payload = await _get_json(session, f"{BASE_URL}{STUDIOS_PATH}")
    if not isinstance(payload, list):
        raise AiFitnessConnectionError("Unexpected studio list payload")

    studios = [s for s in (Studio.from_api(raw) for raw in payload) if s is not None]
    studios.sort(key=lambda s: s.name)
    _LOGGER.debug("Fetched %d AI Fitness studios", len(studios))
    return studios


async def async_get_utilization(
    session: aiohttp.ClientSession, studio_id: str
) -> Utilization:
    """Fetch the utilization for a single studio."""
    url = f"{BASE_URL}{UTILIZATION_PATH.format(studio_id=studio_id)}"
    payload = await _get_json(session, url)
    if not isinstance(payload, dict) or "items" not in payload:
        raise AiFitnessStudioNotFoundError(
            f"No utilization data for studio {studio_id}"
        )
    return Utilization.from_api(payload)
