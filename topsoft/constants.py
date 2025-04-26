from decouple import config

SERVICE = config("SERVICE", default="topsoft")
ACCOUNT = config("ACCOUNT", default="activitysoft_api_key")

MIN_INTERVAL = config("MIN_INTERVAL", default=60, cast=int)
MAX_INTERVAL = config("MAX_INTERVAL", default=86400, cast=int)
DEFAULT_INTERVAL = config("DEFAULT_INTERVAL", default=60, cast=int)
