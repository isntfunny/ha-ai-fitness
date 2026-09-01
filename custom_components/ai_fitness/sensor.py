"""Sensor platform for the AI Fitness integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import LEVELS
from .coordinator import AiFitnessConfigEntry, AiFitnessCoordinator
from .entity import AiFitnessEntity


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: AiFitnessConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AI Fitness sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            AiFitnessUtilizationSensor(coordinator, entry),
            AiFitnessLevelSensor(coordinator, entry),
            AiFitnessPeakSensor(coordinator, entry),
        ]
    )


class AiFitnessUtilizationSensor(AiFitnessEntity, SensorEntity):
    """Current utilization of the studio in percent."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:weight-lifter"

    def __init__(
        self, coordinator: AiFitnessCoordinator, entry: AiFitnessConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "utilization")

    @property
    def native_value(self) -> int | None:
        """Return the utilization of the current time slot."""
        data = self.utilization
        return data.percentage if data else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the full day curve for charting."""
        data = self.utilization
        if data is None:
            return {}
        return {
            "level": data.level,
            "slot_start": data.slot_start,
            "slot_end": data.slot_end,
            "is_open": data.is_open,
            "opens_at": data.day_start,
            "closes_at": data.day_end,
            "peak_percentage": data.peak_percentage,
            "peak_start": data.peak_start,
            # Full day incl. not-yet-elapsed slots (reported as 0 upstream).
            "items": data.items,
            # Only the slots that actually carry measured values.
            "elapsed_items": data.elapsed_items,
        }


class AiFitnessLevelSensor(AiFitnessEntity, SensorEntity):
    """Qualitative utilization level reported by the API."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = LEVELS
    _attr_icon = "mdi:gauge"

    def __init__(
        self, coordinator: AiFitnessCoordinator, entry: AiFitnessConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "level")

    @property
    def native_value(self) -> str | None:
        """Return the level of the current time slot."""
        data = self.utilization
        if data is None or data.level not in LEVELS:
            return None
        return data.level


class AiFitnessPeakSensor(AiFitnessEntity, SensorEntity):
    """Highest utilization expected for the current day."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:chart-bell-curve"
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: AiFitnessCoordinator, entry: AiFitnessConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "peak")

    @property
    def native_value(self) -> int | None:
        """Return the peak utilization of the day."""
        data = self.utilization
        return data.peak_percentage if data else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return when the peak occurs."""
        data = self.utilization
        if data is None:
            return {}
        return {"peak_start": data.peak_start}
