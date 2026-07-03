"""Config flow for the SMS Gammu Gateway integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    GammuGatewayApiClient,
    GammuGatewayAuthError,
    GammuGatewayConnectionError,
    GammuGatewayError,
)
from .const import (
    CONF_SCAN_INTERVAL_SIGNAL,
    CONF_SCAN_INTERVAL_SMS,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL_SIGNAL,
    DEFAULT_SCAN_INTERVAL_SMS,
    DEFAULT_USERNAME,
    DOMAIN,
    MIN_SCAN_INTERVAL_SMS,
)


async def _validate(hass, data) -> str | None:
    """Return an error key, or None if host + credentials are valid."""
    client = GammuGatewayApiClient(
        data[CONF_HOST],
        data[CONF_PORT],
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        async_get_clientsession(hass),
    )
    try:
        # Authenticated endpoint, so wrong credentials fail here (not later
        # on the /getsms poll).
        await client.async_validate_auth()
    except GammuGatewayAuthError:
        return "invalid_auth"
    except (GammuGatewayConnectionError, GammuGatewayError):
        return "cannot_connect"
    return None


class GammuConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            )
            self._abort_if_unique_id_configured()

            error = await _validate(self.hass, user_input)
            if error is None:
                return self.async_create_entry(title="Gammu Gateway", data=user_input)
            errors["base"] = error

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): str,
                vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
                vol.Optional(
                    CONF_SCAN_INTERVAL_SIGNAL, default=DEFAULT_SCAN_INTERVAL_SIGNAL
                ): int,
                vol.Optional(
                    CONF_SCAN_INTERVAL_SMS, default=DEFAULT_SCAN_INTERVAL_SMS
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_SMS)),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_reauth(self, entry_data):
        """Handle re-authentication when the gateway rejects credentials."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Ask the user for new credentials and validate them."""
        errors = {}
        entry = self._reauth_entry

        if user_input is not None:
            new_data = {**entry.data, **user_input}
            error = await _validate(self.hass, new_data)
            if error is None:
                self.hass.config_entries.async_update_entry(entry, data=new_data)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            errors["base"] = error

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME, default=entry.data.get(CONF_USERNAME, DEFAULT_USERNAME)
                ): str,
                vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"host": entry.data.get(CONF_HOST, "")},
        )
