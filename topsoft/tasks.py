import asyncio
import logging

import httpx
from packaging import version
from ttkbootstrap.dialogs import Messagebox

from topsoft.activitysoft.api import post_acessos, sync_students
from topsoft.constants import UPDATE_URL
from topsoft.repository import bulk_update_synced_acessos, get_not_synced_acessos
from topsoft.settings import get_bilhetes_path
from topsoft.utils import (
    get_current_version,
    read_bilhetes_file,
    wait_for_interval,
    wait_until_next_hour,
)

logger = logging.getLogger(__name__)


def task_processamento(stop_event):
    """
    Main background processing task.
    """

    logger.info("Starting background task")
    cnt = 1

    while not stop_event.is_set():
        logger.info(f"Running background task {cnt}")
        cnt += 1

        try:
            # Bilhetes path:
            bilhetes_path = get_bilhetes_path()
            if not bilhetes_path:
                logger.warning("Bilhetes path not found")
                wait_for_interval(stop_event)
                continue

            # Force sync of students:
            if not sync_students():
                logger.error("Failed to update students")
                wait_for_interval(stop_event)
                continue

            # Read and process ticket records (from bilhetes file into database):
            read_bilhetes_file(bilhetes_path, stop_event)

            # Filter out already synced access records:
            acessos = get_not_synced_acessos()

            # Send bilhetes to API:
            results = asyncio.run(post_acessos(acessos))

            # Bulk update access records based on API response:
            bulk_update_synced_acessos(results)

            # TODO: Atualizar interface gráfica
        except Exception as e:
            logger.warning("Error na execução da tarefa")
            logger.exception(e)
        finally:
            wait_for_interval(stop_event)


def task_update_checker(stop_event):
    """
    Check for updates and apply them.
    """

    while not stop_event.is_set():
        try:
            response = httpx.get(UPDATE_URL)

            if response.status_code == 200:
                json_data = response.json()

                if len(json_data) == 0:
                    logger.warning("Empty response from update URL")
                    continue

                release = json_data
                latest_version = version.parse(release["tag_name"])
                assets = release["assets"]

                current_version = version.parse(get_current_version())

                logger.info(f"Versão mais recente: {latest_version}")
                logger.info(f"Versão atual: {current_version}")

                if latest_version > current_version and len(assets) > 0:
                    # TODO: Differentiate between Windows/Linux/MacOS versions
                    logger.warning("Versão instalada não é a mais recente")

                    Messagebox.show_info(
                        title="Atualização", message="Uma nova versão está disponível."
                    )
            else:
                logger.warning(f"Failed to check for updates: {response.status_code}")
        except Exception as e:
            logger.error(f"Error while checking for updates")
            logger.exception(e)
        finally:
            wait_until_next_hour(stop_event)
