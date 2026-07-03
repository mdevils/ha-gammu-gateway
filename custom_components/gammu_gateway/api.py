"""API client for the SMS Gammu Gateway REST server."""
import logging

import aiohttp
import async_timeout

from .const import API_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class GammuGatewayError(Exception):
    """Base error for the Gammu gateway client."""


class GammuGatewayAuthError(GammuGatewayError):
    """Raised when the gateway rejects the credentials (HTTP 401)."""


class GammuGatewayConnectionError(GammuGatewayError):
    """Raised when the gateway cannot be reached or returns an error."""


class GammuGatewayApiClient:
    """Client used to talk to the Gammu gateway REST API."""

    def __init__(self, host, port, username, password, session):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._session = session
        self._base_url = f"http://{host}:{port}"

    async def get_signal(self):
        """Return the signal quality (unauthenticated endpoint)."""
        return await self._api_wrapper("GET", f"{self._base_url}/signal")

    async def get_network(self):
        """Return the network information (unauthenticated endpoint)."""
        return await self._api_wrapper("GET", f"{self._base_url}/network")

    async def get_sms_list(self):
        """Return every SMS currently stored on the modem (authenticated)."""
        result = await self._api_wrapper("GET", f"{self._base_url}/sms")
        return result if isinstance(result, list) else []

    async def get_last_sms(self):
        """Return the oldest stored SMS and remove it from the modem (authenticated)."""
        return await self._api_wrapper("GET", f"{self._base_url}/getsms")

    async def send_sms(self, number, message, smsc=None):
        """Send an SMS (authenticated)."""
        payload = {"number": number, "text": message}
        if smsc:
            payload["smsc"] = smsc
        return await self._api_wrapper("POST", f"{self._base_url}/sms", json_data=payload)

    async def reset_modem(self):
        """Send the reset command to the modem (unauthenticated endpoint)."""
        return await self._api_wrapper("GET", f"{self._base_url}/reset")

    async def async_validate_auth(self):
        """Validate host reachability *and* credentials.

        Calls the authenticated ``/sms`` endpoint so that a wrong
        username/password is detected during setup instead of silently
        failing later on ``/getsms``.
        """
        await self.get_sms_list()

    async def _api_wrapper(self, method, url, json_data=None):
        """Perform the HTTP call, handling Basic authentication and errors."""
        auth = aiohttp.BasicAuth(self._username, self._password)

        try:
            async with async_timeout.timeout(API_TIMEOUT):
                if method == "GET":
                    response = await self._session.get(url, auth=auth)
                else:
                    response = await self._session.post(url, auth=auth, json=json_data)

                if response.status == 401:
                    raise GammuGatewayAuthError(
                        "Authentication failed: wrong username or password"
                    )

                if response.status != 200:
                    text = await response.text()
                    raise GammuGatewayConnectionError(
                        f"Gateway returned HTTP {response.status}: {text}"
                    )

                try:
                    return await response.json()
                except (aiohttp.ContentTypeError, ValueError):
                    # Non-JSON payload (e.g. a textual OK): return the raw body.
                    return {"status": "ok", "raw": await response.text()}

        except GammuGatewayError:
            raise
        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error talking to the Gammu gateway: %s", err)
            raise GammuGatewayConnectionError(f"Connection error: {err}") from err
        except TimeoutError as err:
            _LOGGER.error("Timeout talking to the Gammu gateway: %s", err)
            raise GammuGatewayConnectionError("Timeout talking to the gateway") from err
