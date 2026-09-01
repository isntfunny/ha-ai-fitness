"""Shared entity base for the AI Fitness integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Utilization
from .const import ATTRIBUTION, CONF_STUDIO_NAME, DOMAIN, MANUFACTURER
from .coordinator import AiFitnessConfigEntry, AiFitnessCoordinator


class AiFitnessEntity(CoordinatorEntity[AiFitnessCoordinator]):
    """Base entity carrying the shared device info."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AiFitnessCoordinator,
        entry: AiFitnessConfigEntry,
        key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.data['studio_id']}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data["studio_id"])},
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
