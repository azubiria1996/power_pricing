"""Sensores para Power Pricing."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_TARIFF,
    CONF_TYPE,
    DOMAIN,
    TARIFF_FIXED,
    TARIFF_INDEXED,
    TARIFF_PVPC,
    TARIFF_TOU,
    TARIFF_TYPE_LABELS,
)
from .coordinator import PowerPricingCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crea los sensores para esta config entry."""
    coordinator: PowerPricingCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        PowerPricingCurrentSensor(coordinator, entry),
        PowerPricingMinSensor(coordinator, entry),
        PowerPricingMaxSensor(coordinator, entry),
        PowerPricingMeanSensor(coordinator, entry),
    ])


# ---------------------------------------------------------------------------
# Clase base compartida
# ---------------------------------------------------------------------------

class PowerPricingBaseSensor(CoordinatorEntity[PowerPricingCoordinator], SensorEntity):
    """Sensor base con device info y atributos comunes."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "EUR/kWh"
    _attr_suggested_display_precision = 5
    _attr_icon = "mdi:lightning-bolt"

    def __init__(
        self,
        coordinator: PowerPricingCoordinator,
        entry: ConfigEntry,
        sensor_key: str,
        sensor_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._sensor_key = sensor_key
        tariff_type = entry.data.get(CONF_TARIFF, {}).get(CONF_TYPE, TARIFF_FIXED)

        self._attr_unique_id = f"{entry.entry_id}_{sensor_key}"
        self._attr_name = sensor_name

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Power Pricing",
            model=TARIFF_TYPE_LABELS.get(tariff_type, tariff_type),
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def _stats(self) -> dict[str, Any]:
        return self.coordinator.price_stats or {}


# ---------------------------------------------------------------------------
# Sensor 1: Precio actual
# ---------------------------------------------------------------------------

class PowerPricingCurrentSensor(PowerPricingBaseSensor):
    """Precio €/kWh en la hora actual."""

    def __init__(self, coordinator: PowerPricingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "current_price", "Precio actual")
        self._attr_icon = "mdi:lightning-bolt"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.current_price

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        stats = self._stats
        attrs: dict[str, Any] = {}

        # Estadísticas de HOY
        for key in (
            "today_min", "today_min_at", "today_max", "today_max_at",
            "today_mean", "today_cheap_hours", "today_prices",
        ):
            if key in stats:
                attrs[key] = stats[key]

        # Estadísticas de MAÑANA (disponibles tras ~20:15)
        for key in (
            "tomorrow_min", "tomorrow_min_at", "tomorrow_max", "tomorrow_max_at",
            "tomorrow_mean", "tomorrow_prices",
        ):
            if key in stats:
                attrs[key] = stats[key]

        # Indicadores para automatizaciones
        current = self.coordinator.current_price
        if current is not None and "today_mean" in stats:
            attrs["is_cheap"] = current < stats["today_mean"]
        if current is not None and "today_min" in stats and "today_max" in stats:
            price_range = stats["today_max"] - stats["today_min"]
            if price_range > 0:
                attrs["price_ratio"] = round(
                    (current - stats["today_min"]) / price_range, 3
                )

        return attrs


# ---------------------------------------------------------------------------
# Sensor 2: Precio mínimo del día
# ---------------------------------------------------------------------------

class PowerPricingMinSensor(PowerPricingBaseSensor):
    """Precio mínimo €/kWh del día."""

    def __init__(self, coordinator: PowerPricingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "today_min", "Mínimo hoy")
        self._attr_icon = "mdi:arrow-down-bold"

    @property
    def native_value(self) -> float | None:
        return self._stats.get("today_min")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if "today_min_at" in self._stats:
            attrs["at"] = self._stats["today_min_at"]
        if "tomorrow_min" in self._stats:
            attrs["tomorrow_min"] = self._stats["tomorrow_min"]
            attrs["tomorrow_min_at"] = self._stats["tomorrow_min_at"]
        return attrs


# ---------------------------------------------------------------------------
# Sensor 3: Precio máximo del día
# ---------------------------------------------------------------------------

class PowerPricingMaxSensor(PowerPricingBaseSensor):
    """Precio máximo €/kWh del día."""

    def __init__(self, coordinator: PowerPricingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "today_max", "Máximo hoy")
        self._attr_icon = "mdi:arrow-up-bold"

    @property
    def native_value(self) -> float | None:
        return self._stats.get("today_max")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if "today_max_at" in self._stats:
            attrs["at"] = self._stats["today_max_at"]
        if "tomorrow_max" in self._stats:
            attrs["tomorrow_max"] = self._stats["tomorrow_max"]
            attrs["tomorrow_max_at"] = self._stats["tomorrow_max_at"]
        return attrs


# ---------------------------------------------------------------------------
# Sensor 4: Precio medio del día
# ---------------------------------------------------------------------------

class PowerPricingMeanSensor(PowerPricingBaseSensor):
    """Precio medio €/kWh del día."""

    def __init__(self, coordinator: PowerPricingCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "today_mean", "Media hoy")
        self._attr_icon = "mdi:approximately-equal"

    @property
    def native_value(self) -> float | None:
        return self._stats.get("today_mean")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if "tomorrow_mean" in self._stats:
            attrs["tomorrow_mean"] = self._stats["tomorrow_mean"]
        if "today_cheap_hours" in self._stats:
            attrs["cheap_hours"] = self._stats["today_cheap_hours"]
        return attrs
