"""
Thin async client for the public AI Fitness (Magicline Connect) endpoints.

Both endpoints are public — no authentication, no API key.

The data comes straight from Magicline's Connect API for the ``bestfit``
tenant (the operator behind AI Fitness). Until the November 2026 website
relaunch, ``www.ai-fitness.de/connect/...`` proxied the same routes; those now
return 404, so the integration talks to Magicline directly.

The old ai-fitness.de proxy answered ``406 Not Acceptable`` for
``Accept: application/json``. Magicline itself accepts it, but ``*/*`` keeps
working everywhere, so the headers below stay as they are.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://bestfit.api.magicline.com"
STUDIOS_PATH = "/connect/v2/studio"
UTILIZATION_PATH = "/connect/v1/studio/{studio_id}/utilization"

# Authenticated member API (TOCC / DIRS21 backend behind the app).
APP_BASE_URL = "https://api-allinclusive.tocc.dirs21.de"
TOKEN_PATH = "/v1/oauth2/token"  # noqa: S105 - URL path, not a secret
CHECKINS_YEAR_PATH = "/v1/sportable/statisticsdata/checkins/year"
# The app identifies itself with this fixed public client id. Sending a
# ``scope`` alongside it makes the endpoint answer 501, so never add one.
OAUTH_CLIENT_ID = "AllInclusive"

REQUEST_HEADERS = {
    # A browser-ish UA keeps the CDN happy.
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    # Kept permissive — see module docstring.
    "Accept": "*/*",
}

TIMEOUT = aiohttp.ClientTimeout(total=30)


class AiFitnessError(Exception):
    """Base error for the AI Fitness API."""


class AiFitnessConnectionError(AiFitnessError):
    """Raised when the API cannot be reached."""


class AiFitnessStudioNotFoundError(AiFitnessError):
    """Raised when a studio id yields no utilization data."""


class AiFitnessAuthError(AiFitnessError):
    """Raised when login or token refresh fails."""


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


@dataclass(slots=True)
class TokenBundle:
    """OAuth2 tokens for the member API."""

    access_token: str
    refresh_token: str
    expires_at: float

    @property
    def is_expired(self) -> bool:
        """Return True when the access token is due for renewal."""
        # Renew a minute early so an in-flight request never races expiry.
        return time.time() >= self.expires_at - 60

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> TokenBundle:
        """Build a TokenBundle from a token endpoint response."""
        access = raw.get("access_token")
        refresh = raw.get("refresh_token")
        if not access or not refresh:
            raise AiFitnessAuthError("Token response is missing tokens")
        expires_in = raw.get("expires_in") or 3600
        return cls(
            access_token=str(access),
            refresh_token=str(refresh),
            expires_at=time.time() + float(expires_in),
        )


@dataclass(slots=True)
class Checkin:
    """A single gym visit."""

    date: str
    check_in: str | None
    check_out: str | None
    location: str | None

    @property
    def is_open_visit(self) -> bool:
        """Return True while the member has not checked out again."""
        return self.check_in is not None and self.check_out is None


@dataclass(slots=True)
class CheckinData:
    """Parsed check-in statistics for the current year."""

    year: int
    total_year: int = 0
    total_month: int = 0
    monthly: dict[int, int] = field(default_factory=dict)
    checkins: list[Checkin] = field(default_factory=list)

    @property
    def last(self) -> Checkin | None:
        """Return the most recent visit."""
        return self.checkins[0] if self.checkins else None

    @property
    def currently_in_gym(self) -> bool:
        """Return True when the latest visit has no check-out yet."""
        last = self.last
        return bool(last and last.is_open_visit)

    @classmethod
    def from_api(cls, raw: dict[str, Any], year: int, month: int) -> CheckinData:
        """Build CheckinData from the ``checkins/year`` payload."""
        data = cls(year=year)

        summary = raw.get("Summary") or {}
        data.total_year = int(summary.get("TotalCount") or 0)

        for bucket in raw.get("Breakdown") or []:
            try:
                data.monthly[int(bucket["Key"])] = int(bucket.get("Count") or 0)
            except (KeyError, TypeError, ValueError):
                continue
        data.total_month = data.monthly.get(month, 0)

        visits = [
            Checkin(
                date=str(entry.get("Date") or ""),
                check_in=entry.get("CheckInTime"),
                check_out=entry.get("CheckOutTime"),
                location=entry.get("LocationName"),
            )
            for entry in (raw.get("Checkins") or [])
        ]
        # The API returns newest first, but do not rely on it.
        visits.sort(key=lambda v: (v.date, v.check_in or ""), reverse=True)
        data.checkins = visits
        return data


def _unwrap_envelope(payload: Any) -> dict[str, Any]:
    """
    Unwrap the ``{"Meta": ..., "Value": ...}`` envelope of the member API.

    The backend answers HTTP 200 even for failures and signals the real result
    through ``Meta.IsValid``, so the HTTP status alone must not be trusted.
    """
    if not isinstance(payload, dict):
        raise AiFitnessConnectionError("Unexpected response shape")

    meta = payload.get("Meta") or {}
    value = payload.get("Value")
    if not meta.get("IsValid") or value is None:
        message = meta.get("Message") or "Request rejected by the API"
        raise AiFitnessConnectionError(str(message))
    if not isinstance(value, dict):
        raise AiFitnessConnectionError("Unexpected payload value")
    return value


async def _async_token_request(
    session: aiohttp.ClientSession, form: dict[str, str]
) -> TokenBundle:
    """POST to the token endpoint and parse the result."""
    url = f"{APP_BASE_URL}{TOKEN_PATH}"
    body = {"client_id": OAUTH_CLIENT_ID, **form}
    try:
        async with session.post(
            url, data=body, headers=REQUEST_HEADERS, timeout=TIMEOUT
        ) as response:
            if response.status in (400, 401, 403):
                raise AiFitnessAuthError("Invalid credentials or expired session")
            response.raise_for_status()
            payload = await response.json(content_type=None)
    except aiohttp.ClientError as err:
        raise AiFitnessConnectionError(f"Token request failed: {err}") from err
    except (TimeoutError, ValueError) as err:
        raise AiFitnessConnectionError(f"Bad token response: {err}") from err

    return TokenBundle.from_api(payload)


async def async_login(
    session: aiohttp.ClientSession, username: str, password: str
) -> TokenBundle:
    """Log in with member credentials (OAuth2 password grant)."""
    return await _async_token_request(
        session,
        {"grant_type": "password", "username": username, "password": password},
    )


async def async_refresh_token(
    session: aiohttp.ClientSession, refresh_token: str
) -> TokenBundle:
    """Exchange a refresh token for a fresh token pair."""
    return await _async_token_request(
        session, {"grant_type": "refresh_token", "refresh_token": refresh_token}
    )


async def async_get_checkins(
    session: aiohttp.ClientSession,
    access_token: str,
    year: int,
    month: int,
) -> CheckinData:
    """Fetch this year's check-ins, including the per-month breakdown."""
    url = f"{APP_BASE_URL}{CHECKINS_YEAR_PATH}?year={year}"
    headers = {**REQUEST_HEADERS, "Authorization": f"Bearer {access_token}"}
    try:
        async with session.get(url, headers=headers, timeout=TIMEOUT) as response:
            if response.status in (401, 403):
                raise AiFitnessAuthError("Access token rejected")
            response.raise_for_status()
            payload = await response.json(content_type=None)
    except aiohttp.ClientError as err:
        raise AiFitnessConnectionError(f"Check-in request failed: {err}") from err
    except (TimeoutError, ValueError) as err:
        raise AiFitnessConnectionError(f"Bad check-in response: {err}") from err

    return CheckinData.from_api(_unwrap_envelope(payload), year, month)
