"""Sensor platform for the AI Fitness integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import Checkin
from .const import LEVELS
from .coordinator import (
    AiFitnessCheckinCoordinator,
    AiFitnessConfigEntry,
    AiFitnessCoordinator,
    is_account_entry,
)
from .entity import AiFitnessAccountEntity, AiFitnessStudioEntity


def _visit_start(visit: Checkin) -> datetime | None:
    """Combine a visit's date and check-in time into a local datetime."""
    if not visit.date or not visit.check_in:
        return None
    day = dt_util.parse_datetime(visit.date)
    if day is None:
        return None
    # Times arrive as HH:MM:SS.fffffff (7 fractional digits) in studio-local
    # time; Python only parses up to 6, so trim before handing it over.
    raw = visit.check_in.split(".")[0]
    parsed = dt_util.parse_time(raw)
    if parsed is None:
        return None
    return dt_util.start_of_local_day(day.date()).replace(
        hour=parsed.hour, minute=parsed.minute, second=parsed.second
    )


def _visit_minutes(visit: Checkin) -> int | None:
    """Return the duration of a completed visit in minutes."""
    if not visit.check_in or not visit.check_out:
        return None
    start = dt_util.parse_time(visit.check_in.split(".")[0])
    end = dt_util.parse_time(visit.check_out.split(".")[0])
    if start is None or end is None:
        return None
    minutes = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
    # A visit crossing midnight wraps around.
    if minutes < 0:
        minutes += 24 * 60
    return minutes


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: AiFitnessConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AI Fitness sensors for whichever entry type this is."""
    coordinator = entry.runtime_data

    if is_account_entry(entry):
        async_add_entities(
            [
                AiFitnessCheckinsYearSensor(coordinator, entry),
                AiFitnessCheckinsMonthSensor(coordinator, entry),
                AiFitnessLastCheckinSensor(coordinator, entry),
                AiFitnessLastLocationSensor(coordinator, entry),
                AiFitnessLastDurationSensor(coordinator, entry),
            ]
        )
        return

    async_add_entities(
        [
            AiFitnessUtilizationSensor(coordinator, entry),
            AiFitnessLevelSensor(coordinator, entry),
            AiFitnessPeakSensor(coordinator, entry),
        ]
    )


class AiFitnessUtilizationSensor(AiFitnessStudioEntity, SensorEntity):
    """Current utilization of the studio in percent."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:weight-lifter"

    def __init__(self, coordinator: AiFitnessCoordinator, entry: ConfigEntry) -> None:
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


class AiFitnessLevelSensor(AiFitnessStudioEntity, SensorEntity):
    """Qualitative utilization level reported by the API."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = LEVELS
    _attr_icon = "mdi:gauge"

    def __init__(self, coordinator: AiFitnessCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "level")

    @property
    def native_value(self) -> str | None:
        """Return the level of the current time slot."""
        data = self.utilization
        if data is None or data.level not in LEVELS:
            return None
        return data.level


class AiFitnessPeakSensor(AiFitnessStudioEntity, SensorEntity):
    """Highest utilization measured so far today."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:chart-bell-curve"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AiFitnessCoordinator, entry: ConfigEntry) -> None:
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


class AiFitnessCheckinsYearSensor(AiFitnessAccountEntity, SensorEntity):
    """Number of gym visits in the current year."""

    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:calendar-check"

    def __init__(
        self, coordinator: AiFitnessCheckinCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "checkins_year")

    @property
    def native_value(self) -> int | None:
        """Return this year's visit count."""
        data = self.checkins
        return data.total_year if data else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the per-month breakdown for charting."""
        data = self.checkins
        if data is None:
            return {}
        return {"year": data.year, "monthly": data.monthly}


class AiFitnessCheckinsMonthSensor(AiFitnessAccountEntity, SensorEntity):
    """Number of gym visits in the current month."""

    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:calendar-month"

    def __init__(
        self, coordinator: AiFitnessCheckinCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "checkins_month")

    @property
    def native_value(self) -> int | None:
        """Return this month's visit count."""
        data = self.checkins
        return data.total_month if data else None


class AiFitnessLastCheckinSensor(AiFitnessAccountEntity, SensorEntity):
    """Timestamp of the most recent check-in."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check"

    def __init__(
        self, coordinator: AiFitnessCheckinCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "last_checkin")

    @property
    def native_value(self) -> datetime | None:
        """Return when the last visit started."""
        data = self.checkins
        if data is None or data.last is None:
            return None
        return _visit_start(data.last)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return details about the last visit."""
        data = self.checkins
        if data is None or data.last is None:
            return {}
        last = data.last
        return {
            "location": last.location,
            "check_in": last.check_in,
            "check_out": last.check_out,
            "still_inside": last.is_open_visit,
        }


class AiFitnessLastLocationSensor(AiFitnessAccountEntity, SensorEntity):
    """Studio of the most recent check-in."""

    _attr_icon = "mdi:map-marker"

    def __init__(
        self, coordinator: AiFitnessCheckinCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "last_location")

    @property
    def native_value(self) -> str | None:
        """Return where the last visit took place."""
        data = self.checkins
        if data is None or data.last is None:
            return None
        return data.last.location


class AiFitnessLastDurationSensor(AiFitnessAccountEntity, SensorEntity):
    """Duration of the most recent completed visit."""

    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_icon = "mdi:timer-outline"

    def __init__(
        self, coordinator: AiFitnessCheckinCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "last_duration")

    @property
    def native_value(self) -> int | None:
        """Return how long the last visit lasted."""
        data = self.checkins
        if data is None or data.last is None:
            return None
        return _visit_minutes(data.last)
