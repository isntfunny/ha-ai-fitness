"""Binary sensor platform for the AI Fitness integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import AiFitnessConfigEntry, AiFitnessCoordinator
from .entity import AiFitnessEntity


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: AiFitnessConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AI Fitness binary sensors."""
    async_add_entities([AiFitnessOpenSensor(entry.runtime_data, entry)])


class AiFitnessOpenSensor(AiFitnessEntity, BinarySensorEntity):
    """
    Whether the studio is currently open.

    The API only marks a slot as current during opening hours, so the presence
    of a current slot is the open/closed signal.
    """

    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(
        self, coordinator: AiFitnessCoordinator, entry: AiFitnessConfigEntry
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry, "open")

    @property
    def is_on(self) -> bool | None:
        """Return True when the studio is open."""
        data = self.utilization
        return data.is_open if data else None
