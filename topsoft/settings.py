import logging

from pickledb import PickleDB

from topsoft.constants import (
    DEFAULT_INTERVAL,
    MAX_INTERVAL,
    MIN_INTERVAL,
    SETTINGS_FILE,
)

logger = logging.getLogger(__name__)


_db = PickleDB(SETTINGS_FILE)


def get_or_set(key: str, default):
    if _db.get(key) is None:
        _db.set(key, default)
    return _db.get(key)


def get_bilhetes_path() -> str:
    return get_or_set("bilhetes_path", "")


def set_bilhetes_path(path: str) -> None:
    _db.set("bilhetes_path", path)


def get_interval() -> int:
    return get_or_set("interval", DEFAULT_INTERVAL)


def set_interval(interval: int) -> None:
    interval = max(MIN_INTERVAL, min(interval, MAX_INTERVAL))
    _db.set("interval", interval)
