"""DataUpdateCoordinators for the AI Fitness integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    AiFitnessAuthError,
    AiFitnessError,
    CheckinData,
    TokenBundle,
    Utilization,
    async_get_checkins,
    async_get_utilization,
    async_login,
    async_refresh_token,
)
from .const import (
    CONF_ENTRY_TYPE,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_ACCOUNT_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENTRY_TYPE_ACCOUNT,
)

_LOGGER = logging.getLogger(__name__)

# runtime_data holds whichever coordinator matches the entry type.
AiFitnessConfigEntry = ConfigEntry


def is_account_entry(entry: ConfigEntry) -> bool:
    """Return True when the entry is a member account rather than a studio."""
    return entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_ACCOUNT


class AiFitnessCoordinator(DataUpdateCoordinator[Utilization]):
    """Poll the public utilization endpoint for one studio."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        studio_id: str,
    ) -> None:
        """Initialize the coordinator."""
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {studio_id}",
            update_interval=timedelta(minutes=interval),
        )
        self.studio_id = studio_id
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> Utilization:
        """Fetch the current utilization."""
        try:
            return await async_get_utilization(self._session, self.studio_id)
        except AiFitnessError as err:
            raise UpdateFailed(str(err)) from err


class AiFitnessCheckinCoordinator(DataUpdateCoordinator[CheckinData]):
    """
    Poll the member API for check-in statistics.

    Holds the OAuth2 tokens and refreshes them transparently. The backend
    rotates the refresh token on every use, so the newest one is written back
    into the config entry.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        username: str,
        password: str,
    ) -> None:
        """Initialize the coordinator."""
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_ACCOUNT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {username}",
            update_interval=timedelta(minutes=interval),
        )
        self._entry = entry
        self._username = username
        self._password = password
        self._session = async_get_clientsession(hass)
        self._tokens: TokenBundle | None = None

    def _store_tokens(self, tokens: TokenBundle) -> None:
        """Keep the rotated refresh token across restarts."""
        self._tokens = tokens
        if self._entry.data.get(CONF_REFRESH_TOKEN) == tokens.refresh_token:
            return
        self.hass.config_entries.async_update_entry(
            self._entry,
            data={**self._entry.data, CONF_REFRESH_TOKEN: tokens.refresh_token},
        )

    async def _async_ensure_token(self) -> str:
        """Return a valid access token, refreshing or re-logging in as needed."""
        if self._tokens is not None and not self._tokens.is_expired:
            return self._tokens.access_token

        stored = (
            self._tokens.refresh_token
            if self._tokens
            else self._entry.data.get(CONF_REFRESH_TOKEN)
        )
        if stored:
            try:
                tokens = await async_refresh_token(self._session, stored)
            except AiFitnessAuthError:
                _LOGGER.debug("Refresh token rejected, falling back to password login")
            else:
                self._store_tokens(tokens)
                return tokens.access_token

        try:
            tokens = await async_login(self._session, self._username, self._password)
        except AiFitnessAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        self._store_tokens(tokens)
        return tokens.access_token

    async def _async_update_data(self) -> CheckinData:
        """Fetch this year's check-ins."""
        now = dt_util.now()
        try:
            token = await self._async_ensure_token()
            return await async_get_checkins(self._session, token, now.year, now.month)
        except AiFitnessAuthError as err:
            # Token went stale mid-flight; drop it so the next run re-logs in.
            self._tokens = None
            raise ConfigEntryAuthFailed(str(err)) from err
        except AiFitnessError as err:
            raise UpdateFailed(str(err)) from err
