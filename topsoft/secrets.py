import keyring

from topsoft.constants import ACCOUNT, SERVICE

_cached_api_key: str | None = None


def get_api_key() -> str | None:
    global _cached_api_key
    if _cached_api_key is None:
        _cached_api_key = keyring.get_password(SERVICE, ACCOUNT)
    return _cached_api_key


def set_api_key(api_key: str) -> None:
    global _cached_api_key
    keyring.set_password(SERVICE, ACCOUNT, api_key)
    _cached_api_key = api_key
