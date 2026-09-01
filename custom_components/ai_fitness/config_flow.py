"""Config flow for the AI Fitness integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util.location import distance

from .api import (
    AiFitnessAuthError,
    AiFitnessError,
    Studio,
    async_get_studios,
    async_get_utilization,
    async_login,
)
from .const import (
    CONF_ENTRY_TYPE,
    CONF_QUERY,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_STUDIO_ID,
    CONF_STUDIO_NAME,
    DEFAULT_ACCOUNT_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENTRY_TYPE_ACCOUNT,
    ENTRY_TYPE_STUDIO,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    NEARBY_LIMIT,
    SEARCH_LIMIT,
)

_LOGGER = logging.getLogger(__name__)


def _scan_interval_selector() -> NumberSelector:
    """Return the selector used for the poll interval."""
    return NumberSelector(
        NumberSelectorConfig(
            min=MIN_SCAN_INTERVAL,
            max=MAX_SCAN_INTERVAL,
            step=1,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement="min",
        )
    )


def _studio_label(studio: Studio, distance_km: float | None = None) -> str:
    """Build a human readable dropdown label for a studio."""
    label = studio.name
    if distance_km is not None:
        label = f"{label} — {distance_km:.1f} km"
    if studio.address:
        label = f"{label} · {studio.address}"
    return label


class AiFitnessConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for AI Fitness."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._studios: list[Studio] = []
        self._matches: list[Studio] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:  # noqa: ARG004
        """Return the options flow."""
        return AiFitnessOptionsFlow()

    async def _async_load_studios(self) -> str | None:
        """Load the studio list once. Return an error key on failure."""
        if self._studios:
            return None
        session = async_get_clientsession(self.hass)
        try:
            self._studios = await async_get_studios(session)
        except AiFitnessError as err:
            _LOGGER.warning("Could not load AI Fitness studio list: %s", err)
            return "cannot_connect"
        if not self._studios:
            return "no_studios"
        return None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Let the user pick between a studio and their member account."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["studio", "account"],
        )

    async def async_step_studio(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Let the user choose how to find their studio."""
        return self.async_show_menu(
            step_id="studio",
            menu_options=["nearby", "search", "manual"],
        )

    async def async_step_nearby(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer the studios closest to the Home Assistant location."""
        if error := await self._async_load_studios():
            return self.async_abort(reason=error)

        if user_input is not None:
            return await self._async_create_for_id(user_input[CONF_STUDIO_ID])

        home_lat = self.hass.config.latitude
        home_lon = self.hass.config.longitude

        ranked: list[tuple[float, Studio]] = []
        for studio in self._studios:
            if studio.latitude is None or studio.longitude is None:
                continue
            meters = distance(home_lat, home_lon, studio.latitude, studio.longitude)
            if meters is None:
                continue
            ranked.append((meters / 1000, studio))
        ranked.sort(key=lambda item: item[0])

        if not ranked:
            return await self.async_step_search()

        options = [
            SelectOptionDict(value=studio.id, label=_studio_label(studio, km))
            for km, studio in ranked[:NEARBY_LIMIT]
        ]

        return self.async_show_form(
            step_id="nearby",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STUDIO_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )

    async def async_step_search(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a search term."""
        if error := await self._async_load_studios():
            return self.async_abort(reason=error)

        errors: dict[str, str] = {}

        if user_input is not None:
            query = user_input[CONF_QUERY].strip().casefold()
            self._matches = [
                s
                for s in self._studios
                if query in s.name.casefold()
                or (s.city and query in s.city.casefold())
                or (s.zip_code and query in s.zip_code.casefold())
            ]
            if self._matches:
                return await self.async_step_pick()
            errors["base"] = "no_match"

        return self.async_show_form(
            step_id="search",
            data_schema=vol.Schema({vol.Required(CONF_QUERY): TextSelector()}),
            errors=errors,
        )

    async def async_step_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick one of the search results."""
        if user_input is not None:
            return await self._async_create_for_id(user_input[CONF_STUDIO_ID])

        options = [
            SelectOptionDict(value=s.id, label=_studio_label(s))
            for s in self._matches[:SEARCH_LIMIT]
        ]

        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STUDIO_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
            description_placeholders={"count": str(len(self._matches))},
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Accept a raw studio id."""
        errors: dict[str, str] = {}

        if user_input is not None:
            studio_id = user_input[CONF_STUDIO_ID].strip()
            if not studio_id.isdigit():
                errors["base"] = "invalid_id"
            else:
                return await self._async_create_for_id(studio_id)

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_STUDIO_ID): TextSelector()}),
            errors=errors,
        )

    async def _async_create_for_id(self, studio_id: str) -> ConfigFlowResult:
        """Validate a studio id against the live API and create the entry."""
        await self.async_set_unique_id(studio_id)
        self._abort_if_unique_id_configured()

        session = async_get_clientsession(self.hass)
        try:
            await async_get_utilization(session, studio_id)
        except AiFitnessError as err:
            _LOGGER.warning("Studio %s has no utilization data: %s", studio_id, err)
            return self.async_abort(reason="no_utilization")

        studio = next((s for s in self._studios if s.id == studio_id), None)
        name = studio.name if studio else f"AI Fitness {studio_id}"

        data: dict[str, Any] = {
            CONF_ENTRY_TYPE: ENTRY_TYPE_STUDIO,
            CONF_STUDIO_ID: studio_id,
            CONF_STUDIO_NAME: name,
        }
        if studio is not None:
            data["address"] = studio.address

        return self.async_create_entry(
            title=name,
            data=data,
            options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
        )

    async def async_step_account(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Log in with member credentials to expose check-in data."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            session = async_get_clientsession(self.hass)
            try:
                tokens = await async_login(session, username, password)
            except AiFitnessAuthError:
                errors["base"] = "invalid_auth"
            except AiFitnessError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(username.casefold())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=username,
                    data={
                        CONF_ENTRY_TYPE: ENTRY_TYPE_ACCOUNT,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_REFRESH_TOKEN: tokens.refresh_token,
                    },
                    options={CONF_SCAN_INTERVAL: DEFAULT_ACCOUNT_SCAN_INTERVAL},
                )

        return self.async_show_form(
            step_id="account",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): TextSelector(),
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Handle an expired or revoked login."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the password again and update the entry."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            username = entry.data[CONF_USERNAME]

            session = async_get_clientsession(self.hass)
            try:
                tokens = await async_login(session, username, password)
            except AiFitnessAuthError:
                errors["base"] = "invalid_auth"
            except AiFitnessError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={
                        **entry.data,
                        CONF_PASSWORD: password,
                        CONF_REFRESH_TOKEN: tokens.refresh_token,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
            description_placeholders={"username": entry.data[CONF_USERNAME]},
        )


class AiFitnessOptionsFlow(OptionsFlow):
    """Handle the options flow for AI Fitness."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the poll interval."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])},
            )

        default = (
            DEFAULT_ACCOUNT_SCAN_INTERVAL
            if self.config_entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_ACCOUNT
            else DEFAULT_SCAN_INTERVAL
        )
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, default)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=current
                    ): _scan_interval_selector()
                }
            ),
        )
