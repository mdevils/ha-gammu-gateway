"""Constants for the SMS Gammu Gateway integration."""

DOMAIN = "gammu_gateway"

# Keys inside hass.data[DOMAIN].
DATA_ENTRIES = "entries"
DATA_FRONTEND = "frontend_registered"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Interval to refresh the sensors (signal, network).
CONF_SCAN_INTERVAL_SIGNAL = "scan_interval_signal"

# Interval to poll the gateway for new incoming SMS.
CONF_SCAN_INTERVAL_SMS = "scan_interval_sms"

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "password"
DEFAULT_PORT = 5000

DEFAULT_SCAN_INTERVAL_SIGNAL = 30
DEFAULT_SCAN_INTERVAL_SMS = 20

MIN_SCAN_INTERVAL_SMS = 10

# Network timeout (seconds) for calls to the gateway.
API_TIMEOUT = 10

# Event fired when a new SMS arrives (kept for backwards compatibility).
EVENT_GAMMU_RECEIVED = "gammu_gateway_sms_received"

# Dispatcher signal fired when the stored message list changes.
SIGNAL_MESSAGES_UPDATED = f"{DOMAIN}_messages_updated"

# Persistent storage for received/sent message history.
STORAGE_VERSION = 1
STORAGE_KEY_TEMPLATE = f"{DOMAIN}.messages.{{entry_id}}"

# Maximum number of messages kept in history / exposed as sensor attributes.
MAX_STORED_MESSAGES = 200
MAX_SENSOR_MESSAGES = 50

# Message directions.
DIRECTION_INBOUND = "inbound"
DIRECTION_OUTBOUND = "outbound"

# Services.
SERVICE_SEND_SMS = "send_sms"
SERVICE_CLEAR_MESSAGES = "clear_messages"
SERVICE_DELETE_MESSAGE = "delete_message"

# Frontend cards bundled with the integration.
FRONTEND_SCRIPT_URL = f"/{DOMAIN}/gammu-cards.js"
