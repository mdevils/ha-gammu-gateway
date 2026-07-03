"""Persistent storage for received/sent SMS history."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    DIRECTION_INBOUND,
    DIRECTION_OUTBOUND,
    MAX_STORED_MESSAGES,
    STORAGE_KEY_TEMPLATE,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class MessageStore:
    """Keeps a bounded, persisted list of SMS messages for one config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._hass = hass
        self._store: Store = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY_TEMPLATE.format(entry_id=entry_id),
        )
        self._messages: list[dict[str, Any]] = []
        self._next_id: int = 1

    async def async_load(self) -> None:
        """Load persisted messages from disk."""
        data = await self._store.async_load()
        if data:
            self._messages = data.get("messages", [])
            self._next_id = data.get("next_id", len(self._messages) + 1)

    @property
    def messages(self) -> list[dict[str, Any]]:
        """Return messages, newest first."""
        return self._messages

    def _allocate_id(self) -> int:
        message_id = self._next_id
        self._next_id += 1
        return message_id

    async def async_add_inbound(
        self, number: str, text: str, date: str | None, state: str | None
    ) -> dict[str, Any]:
        """Store a received message and return it."""
        message = {
            "id": self._allocate_id(),
            "direction": DIRECTION_INBOUND,
            "number": number,
            "text": text,
            "date": date,
            "state": state,
        }
        await self._async_prepend(message)
        return message

    async def async_add_outbound(self, number: str, text: str, date: str) -> dict[str, Any]:
        """Store a sent message and return it."""
        message = {
            "id": self._allocate_id(),
            "direction": DIRECTION_OUTBOUND,
            "number": number,
            "text": text,
            "date": date,
            "state": "Sent",
        }
        await self._async_prepend(message)
        return message

    async def _async_prepend(self, message: dict[str, Any]) -> None:
        self._messages.insert(0, message)
        if len(self._messages) > MAX_STORED_MESSAGES:
            self._messages = self._messages[:MAX_STORED_MESSAGES]
        await self._async_save()

    async def async_delete(self, message_id: int) -> bool:
        """Remove a single message by id. Returns True if something was removed."""
        before = len(self._messages)
        self._messages = [m for m in self._messages if m.get("id") != message_id]
        if len(self._messages) != before:
            await self._async_save()
            return True
        return False

    async def async_clear(self) -> None:
        """Remove every stored message."""
        self._messages = []
        await self._async_save()

    async def _async_save(self) -> None:
        await self._store.async_save(
            {"messages": self._messages, "next_id": self._next_id}
        )

    async def async_remove(self) -> None:
        """Delete the on-disk storage (used when the entry is removed)."""
        await self._store.async_remove()
