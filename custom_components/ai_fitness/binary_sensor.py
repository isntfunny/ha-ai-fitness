"""Binary sensor platform for the AI Fitness integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import (
    AiFitnessCheckinCoordinator,
    AiFitnessConfigEntry,
    AiFitnessCoordinator,
    is_account_entry,
)
from .entity import AiFitnessAccountEntity, AiFitnessStudioEntity


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: AiFitnessConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AI Fitness binary sensors."""
    coordinator = entry.runtime_data

    if is_account_entry(entry):
        async_add_entities([AiFitnessInGymSensor(coordinator, entry)])
        return

    async_add_entities([AiFitnessOpenSensor(coordinator, entry)])


class AiFitnessOpenSensor(AiFitnessStudioEntity, BinarySensorEntity):
    """
    Whether the studio is currently open.

    The API only marks a slot as current during opening hours, so the presence
    of a current slot is the open/closed signal.
    """

    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(self, coordinator: AiFitnessCoordinator, entry: ConfigEntry) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry, "open")

    @property
    def is_on(self) -> bool | None:
        """Return True when the studio is open."""
        data = self.utilization
        return data.is_open if data else None


class AiFitnessInGymSensor(AiFitnessAccountEntity, BinarySensorEntity):
    """
    Whether the member is currently checked in somewhere.

    A visit that has a check-in but no check-out yet means the turnstile has
    not seen the member leave.
    """

    _attr_device_class = BinarySensorDeviceClass.PRESENCE
    _attr_icon = "mdi:dumbbell"

    def __init__(
        self, coordinator: AiFitnessCheckinCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry, "in_gym")

    @property
    def is_on(self) -> bool | None:
        """Return True while the member is inside a studio."""
        data = self.checkins
        return data.currently_in_gym if data else None
