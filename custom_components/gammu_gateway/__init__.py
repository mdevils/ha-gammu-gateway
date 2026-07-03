"""The SMS Gammu Gateway integration."""
from __future__ import annotations

import logging
import os

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GammuGatewayApiClient, GammuGatewayError
from .const import (
    CONF_SCAN_INTERVAL_SIGNAL,
    CONF_SCAN_INTERVAL_SMS,
    DATA_ENTRIES,
    DATA_FRONTEND,
    DEFAULT_SCAN_INTERVAL_SIGNAL,
    DEFAULT_SCAN_INTERVAL_SMS,
    DOMAIN,
    FRONTEND_SCRIPT_URL,
    SERVICE_CLEAR_MESSAGES,
    SERVICE_DELETE_MESSAGE,
    SERVICE_SEND_SMS,
)
from .coordinator import GammuGatewayCoordinator
from .store import MessageStore

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "button"]

SERVICE_SEND_SMS_SCHEMA = vol.Schema(
    {
        vol.Required("number"): cv.string,
        vol.Required("message"): cv.string,
        vol.Optional("smsc"): cv.string,
        vol.Optional("entry_id"): cv.string,
    }
)

SERVICE_DELETE_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required("message_id"): vol.Coerce(int),
        vol.Optional("entry_id"): cv.string,
    }
)

SERVICE_CLEAR_MESSAGES_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    session = async_get_clientsession(hass)
    client = GammuGatewayApiClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session,
    )

    store = MessageStore(hass, entry.entry_id)
    await store.async_load()

    coordinator = GammuGatewayCoordinator(
        hass,
        entry.entry_id,
        client,
        store,
        signal_interval=entry.data.get(
            CONF_SCAN_INTERVAL_SIGNAL, DEFAULT_SCAN_INTERVAL_SIGNAL
        ),
        sms_interval=entry.data.get(
            CONF_SCAN_INTERVAL_SMS, DEFAULT_SCAN_INTERVAL_SMS
        ),
    )
    await coordinator.async_config_entry_first_refresh()

    domain_data = hass.data.setdefault(DOMAIN, {DATA_ENTRIES: {}})
    domain_data[DATA_ENTRIES][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    coordinator.start_sms_polling()

    await _async_register_frontend(hass)
    _async_register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    domain_data = hass.data.get(DOMAIN, {})
    coordinator: GammuGatewayCoordinator | None = domain_data.get(
        DATA_ENTRIES, {}
    ).get(entry.entry_id)
    if coordinator is not None:
        coordinator.stop_sms_polling()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        domain_data.get(DATA_ENTRIES, {}).pop(entry.entry_id, None)
        if not domain_data.get(DATA_ENTRIES):
            _async_unregister_services(hass)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete persisted message history when the entry is removed."""
    store = MessageStore(hass, entry.entry_id)
    await store.async_remove()


def _resolve_coordinator(
    hass: HomeAssistant, call: ServiceCall
) -> GammuGatewayCoordinator:
    """Return the coordinator targeted by a service call."""
    entries: dict[str, GammuGatewayCoordinator] = hass.data.get(DOMAIN, {}).get(
        DATA_ENTRIES, {}
    )
    if not entries:
        raise HomeAssistantError("No Gammu Gateway is configured")

    entry_id = call.data.get("entry_id")
    if entry_id is not None:
        coordinator = entries.get(entry_id)
        if coordinator is None:
            raise HomeAssistantError(f"Unknown Gammu Gateway entry_id: {entry_id}")
        return coordinator

    if len(entries) > 1:
        raise HomeAssistantError(
            "Multiple Gammu Gateways are configured; specify 'entry_id'"
        )
    return next(iter(entries.values()))


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the domain-level services (only once)."""
    if hass.services.has_service(DOMAIN, SERVICE_SEND_SMS):
        return

    async def send_sms_service(call: ServiceCall) -> None:
        coordinator = _resolve_coordinator(hass, call)
        try:
            await coordinator.async_send_sms(
                call.data["number"], call.data["message"], call.data.get("smsc")
            )
        except GammuGatewayError as err:
            raise HomeAssistantError(f"Failed to send SMS: {err}") from err

    async def clear_messages_service(call: ServiceCall) -> None:
        coordinator = _resolve_coordinator(hass, call)
        await coordinator.async_clear_messages()

    async def delete_message_service(call: ServiceCall) -> None:
        coordinator = _resolve_coordinator(hass, call)
        await coordinator.async_delete_message(call.data["message_id"])

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_SMS, send_sms_service, schema=SERVICE_SEND_SMS_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_MESSAGES,
        clear_messages_service,
        schema=SERVICE_CLEAR_MESSAGES_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_MESSAGE,
        delete_message_service,
        schema=SERVICE_DELETE_MESSAGE_SCHEMA,
    )


def _async_unregister_services(hass: HomeAssistant) -> None:
    """Remove the domain-level services when the last entry is unloaded."""
    for service in (SERVICE_SEND_SMS, SERVICE_CLEAR_MESSAGES, SERVICE_DELETE_MESSAGE):
        hass.services.async_remove(DOMAIN, service)


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve and register the bundled Lovelace cards (only once)."""
    domain_data = hass.data.setdefault(DOMAIN, {DATA_ENTRIES: {}})
    if domain_data.get(DATA_FRONTEND):
        return
    # Set the flag before awaiting so concurrent entry setups do not both try
    # to register the same static path (the second call would raise).
    domain_data[DATA_FRONTEND] = True

    from homeassistant.components.http import StaticPathConfig

    card_path = os.path.join(os.path.dirname(__file__), "www", "gammu-cards.js")
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_SCRIPT_URL, card_path, True)]
    )

    try:
        from homeassistant.components.frontend import add_extra_js_url

        add_extra_js_url(hass, FRONTEND_SCRIPT_URL)
    except ImportError:  # pragma: no cover - frontend always present in practice
        _LOGGER.warning("Frontend not available; Gammu cards not auto-registered")
