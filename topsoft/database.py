import keyring
import pickledb

from topsoft.constants import ACCOUNT, SERVICE

db = pickledb.load("settings.db", auto_dump=True)


def get_or_set(db, key, default):
    if not db.exists(key):
        db.set(key, default)
    return db.get(key)


def get_api_key():
    """Retrieve from cache or OS vault if not yet loaded."""

    if not hasattr(get_api_key, "_cached"):
        secret = keyring.get_password(SERVICE, ACCOUNT)
        if secret is None:
            raise RuntimeError("API key not set in keyring")
        get_api_key._cached = secret

    return get_api_key._cached


def get_bilhetes_path():
    # TODO: Use fast/not_a_database to store config instead of JSON

    """Retrieve the path to the bilhetes file."""
    bilhetes_path = get_or_set(db, "bilhetes_path", None)
    return bilhetes_path


def get_interval():
    """Retrieve the interval for the background task."""
    interval = get_or_set(db, "interval", 60)
    return interval


def set_bilhetes_path(path):
    """Set the path to the bilhetes file."""
    db.set("bilhetes_path", path)
    db.dump()


def set_interval(interval):
    """Set the interval for the background task."""
    db.set("interval", interval)
    db.dump()


def set_api_key(api_key):
    """Set the API key in the OS vault."""
    keyring.set_password(SERVICE, ACCOUNT, api_key)
    get_api_key._cached = api_key
