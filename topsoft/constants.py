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
UPDATE_URL = config(
    "UPDATE_URL",
    default="https://api.github.com/repos/viniciusccosta/topsoft/releases/latest",
)
