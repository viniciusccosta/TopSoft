import asyncio
import logging
from datetime import datetime

import httpx
from packaging import version

from topsoft.constants import UPDATE_URL
from topsoft.repository import get_not_synced_acessos
from topsoft.settings import get_bilhetes_path, get_cutoff
from topsoft.utils import (
    fetch_and_sync_students,
    get_current_version,
    ingest_bilhetes,
    post_acessos_and_update_synced_status,
    wait_for_interval,
    wait_until_next_hour,
)

logger = logging.getLogger(__name__)


def task_processamento(stop_event, queue):
    """
    Main background processing task.
    """

    logger.info("Starting background processing task")

    while not stop_event.is_set():
        try:
            # 1 ========================================================================
            # Bilhetes path:
            logger.debug("Fetching bilhetes path")

            bilhetes_path = get_bilhetes_path()
            if not bilhetes_path or bilhetes_path == "":
                logger.warning("Bilhetes path not found")
                continue

            # Check if the stop event is set before proceeding:
            if stop_event.is_set():
                break

            # 2 ========================================================================
            # Fetch alunos (from API) and sync them to the database:
            logger.debug("Fetching and syncing students")

            # Attempt to fetch and sync students:
            if not fetch_and_sync_students():
                logger.error("Failed to update students")
                continue

            # Check if the stop event is set before proceeding:
            if stop_event.is_set():
                break

            # 3 ========================================================================
            # Read and process ticket records (from bilhetes file into database):
            logger.debug(f"Reading bilhetes from {bilhetes_path}")

            # Attempt to ingest bilhetes:
            ingest_bilhetes(bilhetes_path, stop_event, batch_size=25000)

            # Check if the stop event is set after processing bilhetes:
            if stop_event.is_set():
                break

            # 4 ========================================================================
            # Filter out already synced access records:
            logger.debug("Fetching not synced access records")

            # Fetch access records that are not synced (from the database):
            acessos = get_not_synced_acessos()
            logger.info(f"Found {len(acessos)} not synced access records")

            if stop_event.is_set():
                break

            # 5 ========================================================================
            # Filter out old records based on cutoff:
            logger.debug("Filtering access records based on cutoff date")

            cutoff = datetime.strptime(get_cutoff(), "%d/%m/%Y").date()
            acessos = [a for a in acessos if a.date >= cutoff]
            logger.info(f"Filtered {len(acessos)} acessos before cutoff date {cutoff}")

            if stop_event.is_set():
                break

            # 6 ========================================================================
            # Send bilhetes to API and update their synced status on the database:
            logger.debug("Posting access records to API and updating synced status")
            results = asyncio.run(post_acessos_and_update_synced_status(acessos))

            # Put the successfully processed access records into the queue:
            queue.put([acesso.id for acesso in results])
            logger.debug(f"Put {len(results)} access records into the queue")
        except Exception as e:
            logger.warning(f"Error na execução da tarefa: {e}")
            logger.exception(e)
        finally:
            wait_for_interval(stop_event)


def task_update_checker(stop_event):
    """
    Check for updates and apply them.
    """

    while not stop_event.is_set():
        try:
            # Fetch the latest release information from the update URL:
            response = httpx.get(UPDATE_URL)

            # Check if the response is successful:
            if response.status_code != 200:
                logger.warning(f"Failed to check for updates: {response.status_code}")
                continue

            # Parse the JSON response:
            json_data = response.json()
            if len(json_data) == 0:
                logger.warning("Empty response from update URL")
                continue

            # Extract the latest release information:
            latest_version = version.parse(json_data["tag_name"])

            # Get the current version from the settings:
            current_version = version.parse(get_current_version())

            if latest_version > current_version:
                # TODO: Differentiate between Windows/Linux/MacOS versions
                logger.warning("Versão instalada não é a mais recente")
                logger.warning(f"Versão mais recente: {latest_version}")
                logger.warning(f"Versão atual: {current_version}")

                # TODO: Alert the user about the new version (using the main GUI thread):
                # Messagebox.show_info(
                #     title="Atualização", message="Uma nova versão está disponível."
                # )
        except Exception as e:
            logger.error(f"Error while checking for updates")
            logger.exception(e)
        finally:
            wait_until_next_hour(stop_event)
