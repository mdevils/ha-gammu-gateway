"""Sensor platform for the SMS Gammu Gateway integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_HOST, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_ENTRIES, DOMAIN, MAX_SENSOR_MESSAGES
from .coordinator import GammuGatewayCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensors."""
    coordinator: GammuGatewayCoordinator = hass.data[DOMAIN][DATA_ENTRIES][
        entry.entry_id
    ]
    host = entry.data[CONF_HOST]

    async_add_entities(
        [
            GammuSignalSensor(coordinator, entry.entry_id, host),
            GammuNetworkSensor(
                coordinator, entry.entry_id, host, "NetworkName", "Operator", "mdi:radio-tower"
            ),
            GammuNetworkSensor(
                coordinator, entry.entry_id, host, "State", "Network State", "mdi:signal-variant"
            ),
            GammuNetworkSensor(
                coordinator, entry.entry_id, host, "NetworkCode", "Network Code", "mdi:numeric"
            ),
            GammuMessagesSensor(coordinator, entry.entry_id, host),
        ]
    )


class GammuBaseEntity(CoordinatorEntity):
    """Base class that groups the entities under a single device."""

    def __init__(self, coordinator, entry_id, host):
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._host = host

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": f"Gammu Gateway ({self._host})",
            "manufacturer": "Gammu",
            "model": "SMS Gateway",
            "configuration_url": f"http://{self._host}:5000",
        }


class GammuSignalSensor(GammuBaseEntity, SensorEntity):
    """Signal strength sensor."""

    def __init__(self, coordinator, entry_id, host):
        super().__init__(coordinator, entry_id, host)
        self._attr_name = "Signal Strength"
        self._attr_unique_id = f"{entry_id}_signal_strength"
        self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
        self._attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        return self.coordinator.data.get("signal", {}).get("SignalStrength")


class GammuNetworkSensor(GammuBaseEntity, SensorEntity):
    """Generic network info sensor (operator, state, code)."""

    def __init__(self, coordinator, entry_id, host, json_key, name_suffix, icon):
        super().__init__(coordinator, entry_id, host)
        self._json_key = json_key
        self._attr_name = name_suffix
        self._attr_unique_id = f"{entry_id}_{json_key.lower()}"
        self._attr_icon = icon

    @property
    def native_value(self):
        return self.coordinator.data.get("network", {}).get(self._json_key)


class GammuMessagesSensor(GammuBaseEntity, SensorEntity):
    """Exposes the stored SMS history for the Lovelace card / templates."""

    def __init__(self, coordinator, entry_id, host):
        super().__init__(coordinator, entry_id, host)
        self._attr_name = "SMS Messages"
        self._attr_unique_id = f"{entry_id}_messages"
        self._attr_icon = "mdi:message-text"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    async def async_added_to_hass(self) -> None:
        """Subscribe to message-store change notifications."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.coordinator.signal_updated_topic,
                self.async_write_ha_state,
            )
        )

    @property
    def native_value(self):
        """Number of messages currently stored."""
        return len(self.coordinator.store.messages)

    @property
    def extra_state_attributes(self):
        messages = self.coordinator.store.messages
        latest = messages[0] if messages else None
        return {
            "messages": messages[:MAX_SENSOR_MESSAGES],
            "last_message": latest.get("text") if latest else None,
            "last_sender": latest.get("number") if latest else None,
            "last_direction": latest.get("direction") if latest else None,
        }
