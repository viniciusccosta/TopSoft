import asyncio
import logging
from datetime import datetime
from queue import Empty

from topsoft.models import Acesso
from topsoft.settings import get_bilhetes_path, get_cutoff
from topsoft.utils import (
    fetch_and_sync_students,
    post_acessos_and_update_synced_status,
    process_events_to_database,
    read_bilhetes_fast,
    wait_for_interval,
)

logger = logging.getLogger(__name__)


# Task 1: Fast file reader and queueing new transactions
def task_file_reader(stop_event, queue):
    """
    Reads the bilhetes file as fast as possible, detects new transactions, and queues them for DB insertion.
    This task only reads the file and queues raw data - no database operations.
    """
    logger.info("Starting file reader task")
    queue.put(
        ("TASK_STATUS", ("file_reader", "running", "Iniciando leitor de arquivo..."))
    )

    while not stop_event.is_set():
        try:
            bilhetes_path = get_bilhetes_path()
            if not bilhetes_path or bilhetes_path == "":
                logger.warning("Bilhetes path not found")
                queue.put(
                    (
                        "TASK_STATUS",
                        (
                            "file_reader",
                            "error",
                            "Caminho do arquivo bilhetes não encontrado",
                        ),
                    )
                )
                wait_for_interval(stop_event)
                continue

            # Fast file reading without database operations
            logger.debug(f"Fast reading bilhetes from {bilhetes_path}")
            queue.put(
                (
                    "TASK_STATUS",
                    ("file_reader", "running", f"Lendo arquivo: {bilhetes_path}"),
                )
            )

            new_events = read_bilhetes_fast(bilhetes_path, stop_event)

            if new_events:
                logger.info(
                    f"Found {len(new_events)} new events, queueing for processing"
                )
                queue.put(("PROCESS_EVENTS", new_events))
                queue.put(
                    (
                        "TASK_STATUS",
                        (
                            "file_reader",
                            "success",
                            f"Encontrados {len(new_events)} novos eventos",
                        ),
                    )
                )
            else:
                queue.put(
                    (
                        "TASK_STATUS",
                        ("file_reader", "waiting", "Nenhum novo evento encontrado"),
                    )
                )

        except Exception as e:
            logger.warning(f"Error in file reader task: {e}")
            logger.exception(e)
            queue.put(("TASK_STATUS", ("file_reader", "error", f"Erro: {str(e)}")))
        finally:
            wait_for_interval(stop_event)


# Task 2: Process queued events into database
def task_db_processor(stop_event, queue):
    """
    Takes raw events from the queue and processes them into the database.
    This task handles all database insertion operations.
    """
    logger.info("Starting database processor task")
    queue.put(
        (
            "TASK_STATUS",
            ("db_processor", "waiting", "Aguardando eventos para processar..."),
        )
    )

    while not stop_event.is_set():
        try:
            # Check for queued events to process
            try:
                message_type, data = queue.get(timeout=1)  # Wait 1 second for new data

                if message_type == "PROCESS_EVENTS":
                    logger.debug(f"Processing {len(data)} events into database")
                    queue.put(
                        (
                            "TASK_STATUS",
                            (
                                "db_processor",
                                "running",
                                f"Processando {len(data)} eventos no banco...",
                            ),
                        )
                    )

                    processed_records = process_events_to_database(data, stop_event)
                    if processed_records:
                        logger.info(
                            f"Successfully processed {len(processed_records)} records into database"
                        )
                        queue.put(
                            (
                                "TASK_STATUS",
                                (
                                    "db_processor",
                                    "success",
                                    f"Processados {len(processed_records)} registros com sucesso",
                                ),
                            )
                        )
                    else:
                        queue.put(
                            (
                                "TASK_STATUS",
                                (
                                    "db_processor",
                                    "warning",
                                    "Nenhum registro foi processado",
                                ),
                            )
                        )

            except Empty:
                # No new data, continue loop
                continue

        except Exception as e:
            logger.warning(f"Error in database processor task: {e}")
            logger.exception(e)
            queue.put(("TASK_STATUS", ("db_processor", "error", f"Erro: {str(e)}")))
        finally:
            # Short pause to prevent busy waiting
            if not stop_event.is_set():
                stop_event.wait(0.1)


# Task 3: Sync unsynced DB records to API
def task_db_sync(stop_event, queue):
    """
    Fetches unsynced transactions from the DB and pushes them to the API.
    This task only handles API synchronization.
    """
    logger.info("Starting DB sync task")
    queue.put(
        ("TASK_STATUS", ("db_sync", "running", "Iniciando sincronização com API..."))
    )

    while not stop_event.is_set():
        try:
            # Optionally, fetch and sync students if needed
            logger.debug("Fetching and syncing students")
            queue.put(
                (
                    "TASK_STATUS",
                    ("db_sync", "running", "Sincronizando dados de estudantes..."),
                )
            )
            fetch_and_sync_students()

            logger.debug("Fetching not synced access records")
            queue.put(
                (
                    "TASK_STATUS",
                    ("db_sync", "running", "Buscando registros não sincronizados..."),
                )
            )
            acessos = Acesso.get_unsynced()
            logger.info(f"Found {len(acessos)} not synced access records")

            if acessos:
                cutoff = datetime.strptime(get_cutoff(), "%d/%m/%Y").date()
                acessos = [a for a in acessos if a.date >= cutoff]
                logger.info(
                    f"Filtered {len(acessos)} acessos before cutoff date {cutoff}"
                )

                if acessos:
                    logger.debug(
                        "Posting access records to API and updating synced status"
                    )
                    queue.put(
                        (
                            "TASK_STATUS",
                            (
                                "db_sync",
                                "running",
                                f"Enviando {len(acessos)} registros para API...",
                            ),
                        )
                    )

                    results = asyncio.run(
                        post_acessos_and_update_synced_status(acessos)
                    )

                    if results:
                        queue.put(("SYNC_COMPLETED", [acesso.id for acesso in results]))
                        logger.debug(
                            f"Put {len(results)} synced access records into the queue"
                        )
                        queue.put(
                            (
                                "TASK_STATUS",
                                (
                                    "db_sync",
                                    "success",
                                    f"Sincronizados {len(results)} registros com sucesso",
                                ),
                            )
                        )
                    else:
                        queue.put(
                            (
                                "TASK_STATUS",
                                (
                                    "db_sync",
                                    "warning",
                                    "Nenhum registro foi sincronizado",
                                ),
                            )
                        )
                else:
                    queue.put(
                        (
                            "TASK_STATUS",
                            (
                                "db_sync",
                                "waiting",
                                "Nenhum registro para sincronizar após filtro",
                            ),
                        )
                    )
            else:
                queue.put(
                    (
                        "TASK_STATUS",
                        (
                            "db_sync",
                            "waiting",
                            "Nenhum registro não sincronizado encontrado",
                        ),
                    )
                )

        except Exception as e:
            logger.warning(f"Error in DB sync task: {e}")
            logger.exception(e)
            queue.put(("TASK_STATUS", ("db_sync", "error", f"Erro: {str(e)}")))
        finally:
            wait_for_interval(stop_event)
