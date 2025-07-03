import logging
import os
import sys
from datetime import datetime, timedelta
from os import path
from time import sleep
from typing import List

import toml
from pygtail import Pygtail

from topsoft.activitysoft.api import fetch_students, post_acessos
from topsoft.constants import OFFSET_PATH
from topsoft.models import Acesso
from topsoft.repository import (
    process_turnstile_event,
    update_acesso,
    update_student_records,
)
from topsoft.settings import get_interval

logger = logging.getLogger(__name__)


def get_path(filename):
    """
    Get the correct path for a file, whether running in development or as a PyInstaller executable.
    """

    if hasattr(sys, "_MEIPASS"):
        return path.realpath(path.join(sys._MEIPASS, filename))
    return filename


def get_current_version():
    """
    Get the current version of the application from pyproject.toml.
    """

    try:
        with open("pyproject.toml", "r", encoding="utf-8") as f:
            pyproject_data = toml.load(f)
            return pyproject_data.get("project", {}).get("version", "0.0.0")
    except FileNotFoundError:
        logger.error("pyproject.toml not found")
    except Exception as e:
        logger.error(f"Error reading pyproject.toml: {e}")

    return "0.0.0"


def read_bilhetes_file(
    filepath, stop_event, cutoff=None, force_read=False
) -> List["Acesso"]:
    """
    Reads new lines from the bilhetes file since the last run (or since force_read),
    parses each record, and returns a list of Acesso objects.
    """

    # Variables:
    tickets = []

    # If forcing full re-read, delete the offset file
    if force_read:
        try:
            os.remove(OFFSET_PATH)
            logger.info("Offset file removed; full file will be re-read.")
        except FileNotFoundError:
            pass

    # Read the file using Pygtail:
    reader = Pygtail(filepath, offset_file=OFFSET_PATH, paranoid=True)

    for n, raw_line in enumerate(reader):
        # Check if the stop event is set to stop processing
        if stop_event.is_set():
            logger.info("Stopping extraction of bilhetes")
            return tickets

        # Skip empty lines
        parts = raw_line.strip().split()
        if len(parts) < 5:
            logger.warning(f"Skipping malformed line: {raw_line!r}")
            continue

        # Parse the timestamp from the line
        try:
            parsed_timestamp = datetime.strptime(
                f"{parts[1]} {parts[2]}", "%d/%m/%y %H:%M"
            )
        except ValueError:
            logger.warning(f"Invalid timestamp in line: {raw_line!r}")
            continue

        # If cutoff is set, skip records older than the cutoff
        if cutoff and parsed_timestamp < cutoff:
            continue

        # Create a ticket record from the parts (into database):
        try:
            ticket = process_turnstile_event(
                {
                    "marcacao": parts[0],
                    "date": parts[1],
                    "time": parts[2],
                    "cartao": parts[3],
                    "catraca": parts[4],
                }
            )
            tickets.append(ticket)
        except Exception as e:
            logger.warning(f"Error reading line: {raw_line!r}")
            logger.exception(e)
            continue

    # Return the list of tickets
    return tickets


def wait_for_interval(stop_event):
    """
    Wait for the specified interval before the next processing cycle.
    """

    intervalo = get_interval() * 60

    for i in range(intervalo):
        if stop_event.is_set():
            logger.info("Stopping background task")
            return

        logger.debug(f"Next processing in {intervalo - i} seconds")
        sleep(1)


def wait_until_next_hour(stop_event):
    """
    Wait for the specified interval.
    """

    now = datetime.now()
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    sleep_duration = int((next_hour - now).total_seconds())

    for i in range(sleep_duration):
        if stop_event.is_set():
            logger.info("Stopping update task")
            return

        logger.debug(f"Next update check in {sleep_duration - i} seconds")
        sleep(1)


def fetch_and_sync_students():
    """
    Update the students in the database by fetching and syncing data from the API.
    """

    logger.info("Starting student data synchronization")

    # Fetch students from the API:
    students_data = fetch_students()

    # If fetching failed, log the error and return
    if students_data is None:
        logger.error("Failed to fetch students from the API")
        return False

    # Update database with the fetched student data:
    try:
        update_student_records(students_data)
        logger.info("Student data synchronization completed successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to sync students: {e}")
        return False


async def post_acessos_and_update_synced_status(bilhetes, queue):
    """
    Consume the access records and process them.
    This function is called by the main task to handle the access records.
    """

    async for result in post_acessos(bilhetes):
        acesso, success = result
        if success:
            update_acesso(acesso.id, synced=True)
            queue.put(result)
