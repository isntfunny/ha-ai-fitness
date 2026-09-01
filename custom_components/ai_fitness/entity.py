"""Shared entity bases for the AI Fitness integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import CheckinData, Utilization
from .const import ATTRIBUTION, CONF_STUDIO_ID, CONF_STUDIO_NAME, DOMAIN, MANUFACTURER
from .coordinator import AiFitnessCheckinCoordinator, AiFitnessCoordinator


class AiFitnessStudioEntity(CoordinatorEntity[AiFitnessCoordinator]):
    """Base entity for the anonymous studio utilization entries."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AiFitnessCoordinator,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        studio_id = entry.data[CONF_STUDIO_ID]
        self._attr_translation_key = key
        self._attr_unique_id = f"{studio_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, studio_id)},
            name=entry.data.get(CONF_STUDIO_NAME, entry.title),
            manufacturer=MANUFACTURER,
            model=entry.data.get("address") or None,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.ai-fitness.de/studios",
        )

    @property
    def utilization(self) -> Utilization | None:
        """Return the current utilization payload."""
        return self.coordinator.data


class AiFitnessAccountEntity(CoordinatorEntity[AiFitnessCheckinCoordinator]):
    """Base entity for the authenticated member account entry."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AiFitnessCheckinCoordinator,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        username = entry.data[CONF_USERNAME]
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"account_{entry.entry_id}")},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=username,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def checkins(self) -> CheckinData | None:
        """Return the current check-in payload."""
        return self.coordinator.data
