import logging

from pickledb import PickleDB

from topsoft.constants import (
    DEFAULT_INTERVAL,
    MAX_INTERVAL,
    MIN_INTERVAL,
    SETTINGS_FILE,
)

logger = logging.getLogger(__name__)


sdb = PickleDB(SETTINGS_FILE)

# TODO: Instead of using PickleDB, just add a settings table to the database !


def get_or_set(key: str, default):
    with sdb:
        if sdb.get(key) is None:
            sdb.set(key, default)

    return sdb.get(key)


def get_bilhetes_path() -> str:
    return get_or_set("bilhetes_path", "")


def set_bilhetes_path(path: str) -> None:
    with sdb:
        sdb.set("bilhetes_path", path)


def get_interval() -> int:
    return get_or_set("interval", DEFAULT_INTERVAL)


def set_interval(interval: int) -> None:
    with sdb:
        interval = max(MIN_INTERVAL, min(interval, MAX_INTERVAL))
        sdb.set("interval", interval)


def get_cutoff():
    return get_or_set("cutoff", "01/05/2025")


def set_cutoff(cutoff):
    with sdb:
        sdb.set("cutoff", cutoff)
