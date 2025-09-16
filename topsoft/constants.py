from decouple import config

SERVICE = config("SERVICE", default="topsoft")
ACCOUNT = config("ACCOUNT", default="activitysoft_api_key")

MIN_INTERVAL = config("MIN_INTERVAL", default=1, cast=int)
MAX_INTERVAL = config("MAX_INTERVAL", default=1440, cast=int)
DEFAULT_INTERVAL = config("DEFAULT_INTERVAL", default=1, cast=int)

API_BASE_URL = config(
    "API_BASE_URL",
    default=r"https://siga.activesoft.com.br/api/v0/",
)

SETTINGS_FILE = config("SETTINGS_FILE", default="./settings.json")
OFFSET_PATH = config("OFFSET_PATH", default="./bilhetes.offset")

MAX_AT_ONCE = config("MAX_AT_ONCE", default=1000, cast=int)
MAX_PER_SECOND = config("MAX_PER_SECOND", default=5, cast=int)

# Performance tuning parameters
FILE_READ_CHUNK_SIZE = config("FILE_READ_CHUNK_SIZE", default=10000, cast=int)
DB_BATCH_SIZE = config("DB_BATCH_SIZE", default=5000, cast=int)

# Error handling and backoff configuration
BACKOFF_INTERVALS = [1, 5, 10, 30]  # Minutes: 1min → 5min → 10min → 30min
MAX_BACKOFF_LEVEL = len(BACKOFF_INTERVALS) - 1
