"""Legacy notify platform for the SMS Gammu Gateway integration.

Enable it via ``configuration.yaml``::

    notify:
      - name: sms
        platform: gammu_gateway
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.notify import BaseNotificationService
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DATA_ENTRIES, DOMAIN
from .coordinator import GammuGatewayCoordinator


async def async_get_service(
    hass: HomeAssistant, config: ConfigType, discovery_info=None
):
    """Return the notification service backed by the first configured gateway."""
    entries: dict[str, GammuGatewayCoordinator] = hass.data.get(DOMAIN, {}).get(
        DATA_ENTRIES, {}
    )
    coordinator = next(iter(entries.values()), None)
    if coordinator is None:
        return None
    return SmsGammuNotificationService(coordinator)


class SmsGammuNotificationService(BaseNotificationService):
    """Send SMS messages through the Gammu gateway."""

    def __init__(self, coordinator: GammuGatewayCoordinator):
        self.coordinator = coordinator

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        targets = kwargs.get("target")
        smsc = (kwargs.get("data") or {}).get("smsc")

        if isinstance(targets, str):
            targets = [targets]
        if not targets:
            return

        for number in targets:
            await self.coordinator.async_send_sms(number=number, text=message, smsc=smsc)
