"""DataUpdateCoordinator for the AI Fitness integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AiFitnessError, Utilization, async_get_utilization
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

AiFitnessConfigEntry = ConfigEntry["AiFitnessCoordinator"]


class AiFitnessCoordinator(DataUpdateCoordinator[Utilization]):
    """Poll the public utilization endpoint for one studio."""

    config_entry: AiFitnessConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AiFitnessConfigEntry,
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
