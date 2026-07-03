"""Data update coordinator for the SMS Gammu Gateway integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import GammuGatewayApiClient, GammuGatewayAuthError, GammuGatewayError
from .const import (
    EVENT_GAMMU_RECEIVED,
    SIGNAL_MESSAGES_UPDATED,
)
from .store import MessageStore

_LOGGER = logging.getLogger(__name__)

# Safety cap so a misbehaving gateway cannot spin forever while draining.
MAX_DRAIN_PER_POLL = 25


class GammuGatewayCoordinator(DataUpdateCoordinator):
    """Fetches signal/network data and manages SMS history for one entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        client: GammuGatewayApiClient,
        store: MessageStore,
        signal_interval: int,
        sms_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="gammu_gateway",
            update_interval=timedelta(seconds=signal_interval),
        )
        self.entry_id = entry_id
        self.client = client
        self.store = store
        self._sms_interval = sms_interval
        self._unsub_sms: Any = None

    @property
    def signal_updated_topic(self) -> str:
        """Dispatcher topic fired when the message list changes."""
        return f"{SIGNAL_MESSAGES_UPDATED}_{self.entry_id}"

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch signal and network info (both unauthenticated endpoints)."""
        try:
            signal = await self.client.get_signal()
            network = await self.client.get_network()
        except GammuGatewayError as err:
            raise UpdateFailed(f"Error updating Gammu gateway data: {err}") from err
        return {"signal": signal or {}, "network": network or {}}

    def start_sms_polling(self) -> None:
        """Begin periodic polling of incoming SMS."""
        self._unsub_sms = async_track_time_interval(
            self.hass, self._async_poll_sms, timedelta(seconds=self._sms_interval)
        )

    def stop_sms_polling(self) -> None:
        """Stop periodic SMS polling."""
        if self._unsub_sms is not None:
            self._unsub_sms()
            self._unsub_sms = None

    async def _async_poll_sms(self, _now=None) -> None:
        """Drain the modem's SMS queue via /getsms, storing each message."""
        received = 0
        try:
            for _ in range(MAX_DRAIN_PER_POLL):
                sms = await self.client.get_last_sms()
                text = (sms or {}).get("Text")
                if not text:
                    break

                sender = sms.get("Number") or sms.get("Sender") or "Unknown"
                date = sms.get("Date") or sms.get("DateTime")
                state = sms.get("State")

                await self.store.async_add_inbound(sender, text, date, state)
                received += 1

                _LOGGER.info("New SMS received from %s", sender)
                self.hass.bus.async_fire(
                    EVENT_GAMMU_RECEIVED,
                    {"sender": sender, "text": text, "date": date, "state": state},
                )
        except GammuGatewayAuthError as err:
            _LOGGER.warning("Authentication failed while polling SMS: %s", err)
            self._start_reauth()
        except GammuGatewayError as err:
            _LOGGER.warning("Error while checking for new SMS: %s", err)

        if received:
            self._notify_messages_changed()

    async def async_send_sms(
        self, number: str, text: str, smsc: str | None = None
    ) -> None:
        """Send an SMS and record it in the message history."""
        try:
            await self.client.send_sms(number, text, smsc)
        except GammuGatewayAuthError:
            self._start_reauth()
            raise
        await self.store.async_add_outbound(number, text, dt_util.now().isoformat())
        _LOGGER.info("SMS sent to %s", number)
        self._notify_messages_changed()

    async def async_delete_message(self, message_id: int) -> None:
        """Delete a single message from the stored history."""
        if await self.store.async_delete(message_id):
            self._notify_messages_changed()

    async def async_clear_messages(self) -> None:
        """Clear the stored message history."""
        await self.store.async_clear()
        self._notify_messages_changed()

    @callback
    def _notify_messages_changed(self) -> None:
        async_dispatcher_send(self.hass, self.signal_updated_topic)

    @callback
    def _start_reauth(self) -> None:
        """Kick off the re-authentication flow for this entry."""
        entry = self.hass.config_entries.async_get_entry(self.entry_id)
        if entry is not None:
            entry.async_start_reauth(self.hass)
