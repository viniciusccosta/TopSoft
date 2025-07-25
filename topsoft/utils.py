import logging
import os
import sys
from datetime import datetime, timedelta
from os import path
from time import sleep
from typing import List

import toml
from pygtail import Pygtail

from topsoft.activitysoft.api import get_students_from_api, post_accessos_concurrently
from topsoft.constants import OFFSET_PATH
from topsoft.models import Acesso, Aluno
from topsoft.repository import bulk_process_turnstile_events, process_turnstile_event
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


def ingest_bilhetes(
    filepath,
    stop_event,
    cutoff=None,
    batch_size=1000,
) -> List["Acesso"]:
    """
    Reads new lines from the bilhetes file since the last run (or since force_read), parses each record, and returns a list of Acesso objects.

    Pygtail is used to read the file line by line, allowing it to efficiently handle large files. It also tracks the last read position, making it ideal for scenarios like the "catraca," which only appends new lines to the file

    Parameters:
    - filepath (str): The path to the bilhetes file.
    - stop_event (threading.Event): An event to signal when to stop processing.
    - cutoff (datetime, optional): If set, only records newer than this date will be processed.
    - force_read (bool): If True, the offset file will be deleted, forcing a full re-read of the bilhetes file.
    - batch_size (int): Number of events to process in each batch for bulk insertion.

    Returns:
    - List[Acesso]: A list of Acesso objects created from the parsed records.
    """

    logger.info(f"Ingesting bilhetes from file: {filepath=}")

    # Variables:
    all_tickets = []
    events_batch = []

    # TODO: Would be nice to get how many lines are in the file, so we can log it !

    # Read the file using Pygtail:
    reader = Pygtail(filepath, offset_file=OFFSET_PATH, paranoid=True)

    def process_batch(events):
        """Process a batch of events using bulk insertion"""
        if not events:
            return []

        try:
            return bulk_process_turnstile_events(events)
        except Exception as e:
            logger.error(f"Error processing batch of {len(events)} events: {e}")
            # Fallback to individual processing if bulk fails
            fallback_tickets = []
            for event in events:
                try:
                    ticket = process_turnstile_event(event)
                    if ticket:
                        fallback_tickets.append(ticket)
                except Exception as event_error:
                    logger.warning(
                        f"Error processing individual event: {event}, error: {event_error}"
                    )
            return fallback_tickets

    for n, raw_line in enumerate(reader):
        # Before each raw_line, checks if the stop event is set to stop processing
        if stop_event.is_set():
            logger.info("Stopping extraction of bilhetes")
            # Process any remaining events in the batch before stopping
            if events_batch:
                batch_tickets = process_batch(events_batch)
                all_tickets.extend(batch_tickets)
            return all_tickets

        # Skip empty lines, or malformed lines:
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

        # Add event to batch
        event = {
            "marcacao": parts[0],
            "date": parts[1],
            "time": parts[2],
            "cartao": parts[3],
            "catraca": parts[4],
        }
        events_batch.append(event)

        # Process batch when it reaches the batch size
        if len(events_batch) >= batch_size:
            batch_tickets = process_batch(events_batch)
            all_tickets.extend(batch_tickets)
            events_batch = []  # Reset batch

    # Process any remaining events in the final batch
    if events_batch:
        batch_tickets = process_batch(events_batch)
        all_tickets.extend(batch_tickets)

    logger.info(f"Successfully ingested {len(all_tickets)} tickets.")
    return all_tickets


def wait_for_interval(stop_event):
    """
    Wait for the specified interval before the next processing cycle.

    Parameters:
    - stop_event (threading.Event): An event to signal when to stop waiting.

    Returns:
    - None
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

    Parameters:
    - stop_event (threading.Event): An event to signal when to stop waiting.

    Returns:
    - None
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

    # Log the start of the synchronization process:
    logger.info("Starting student data synchronization")

    # Fetch students from the API:
    try:
        students_data = get_students_from_api()
    except Exception as e:
        logger.error(f"Failed to fetch students: {e}")
        return False

    # Update database with the fetched student data:
    try:
        Aluno.bulk_update_from_json(students_data)
        logger.info("Student data synchronization completed successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to sync students: {e}")
        return False


async def post_acessos_and_update_synced_status(acessos):
    """
    Consume the access records and process them.
    This function is called by the main task to handle the access records.

    Parameters:
    - bilhetes (List[Acesso]): A list of access records to be processed.

    Returns:
    - None
    """

    # Check if there are any access records to process:
    if not acessos:
        logger.info("No access records to process")
        return []

    # Log the start of processing access records:
    logger.info(f"Starting to process {len(acessos)} access records")

    # Post and update the access records:
    try:
        # Post access records to the API:
        logger.debug("Posting access records to the API")
        results = await post_accessos_concurrently(acessos)

        # Filter successful results:
        logger.debug(f"Filtering successful access records from {len(results)} results")
        sucess_results = [r[0] for r in results if r[1] == True]

        # Bulk update the synced status of access records:
        logger.debug(f"Updating synced status for {len(sucess_results)} access records")
        Acesso.bulk_update_synced_status(sucess_results, status=True)

        # Log and return the successfully processed access records:
        logger.info(f"Successfully processed {len(sucess_results)} access records")
        return sucess_results
    except Exception as e:
        logger.error(f"Error in post_acessos_and_update_synced_status: {e}")
        logger.exception(e)
        raise
