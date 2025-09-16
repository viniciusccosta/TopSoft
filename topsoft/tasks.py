import asyncio
import logging
from datetime import datetime
from queue import Empty

from topsoft.models import Acesso
from topsoft.settings import get_bilhetes_path, get_cutoff, get_interval
from topsoft.utils import (
    BACKOFF_INTERVALS,
    MAX_BACKOFF_LEVEL,
    fetch_and_sync_students,
    post_acessos_and_update_synced_status,
    process_events_to_database,
    read_bilhetes_fast,
    wait_for_interval,
    wait_for_interval_with_backoff,
)

logger = logging.getLogger(__name__)


def check_cancellation_frequently(stop_event, operation_name, check_interval=0.1):
    """
    Utility function to check cancellation more frequently during operations.

    Args:
        stop_event: Threading event to check
        operation_name: Name of operation for logging
        check_interval: How often to check (seconds)

    Raises:
        InterruptedError: If operation should be cancelled
    """
    if stop_event.is_set():
        logger.info(f"Operation {operation_name} cancelled by user request")
        raise InterruptedError(f"Operation {operation_name} was cancelled")

    # Small sleep to allow other threads to run
    stop_event.wait(check_interval)


# Task 1: Fast file reader and queueing new transactions
def task_file_reader(stop_event, queue):
    """
    Reads the bilhetes file as fast as possible, detects new transactions, and queues them for DB insertion.
    This task only reads the file and queues raw data - no database operations.
    """
    TASK_ID = "file_reader"

    logger.info("Starting file reader task")
    failure_count = 0

    while not stop_event.is_set():
        try:
            # Check cancellation before starting file operations
            check_cancellation_frequently(stop_event, "file reader", 0.05)

            # Logger debug
            logger.debug("File reader task cycle starting")

            # Send initial start status
            queue.put(
                (
                    "TASK_STATUS",
                    (TASK_ID, "start", "Iniciando leitor de arquivos..."),
                )
            )

            bilhetes_path = get_bilhetes_path()
            if not bilhetes_path or bilhetes_path == "":
                raise FileNotFoundError("Caminho dos bilhetes não configurado")

            # Check cancellation before starting file operations
            check_cancellation_frequently(stop_event, "file reader", 0.05)

            # Fast file reading without database operations
            logger.debug(f'Fast reading bilhetes from "{bilhetes_path}"')
            queue.put(
                (
                    "TASK_STATUS",
                    (TASK_ID, "running", f"Lendo arquivo: {bilhetes_path}"),
                )
            )

            new_events = read_bilhetes_fast(bilhetes_path, stop_event)

            # Check cancellation after file reading
            check_cancellation_frequently(stop_event, "file reader", 0.05)

            if new_events:
                logger.info(
                    f"Found {len(new_events)} new events, queueing for processing"
                )
                queue.put(("PROCESS_EVENTS", new_events))
                queue.put(
                    (
                        "TASK_STATUS",
                        (
                            TASK_ID,
                            "success",
                            f"Encontrados {len(new_events)} novos eventos",
                        ),
                    )
                )
                # Reset failure count on success
                failure_count = 0
            else:
                queue.put(
                    (
                        "TASK_STATUS",
                        (TASK_ID, "success", "Nenhum novo evento encontrado"),
                    )
                )
                # Reset failure count on successful read (even if no new events)
                failure_count = 0
        except InterruptedError:
            # Handle cancellation gracefully
            logger.info("File reader task cancelled")
            queue.put(("TASK_STATUS", (TASK_ID, "cancelled", "Tarefa cancelada")))
            break
        except Exception as e:
            failure_count += 1
            logger.warning(f"Error in file reader task (failure #{failure_count}): {e}")
            if failure_count <= 3:  # Only log full exception for first few failures
                logger.exception(e)
            queue.put(
                (
                    "TASK_STATUS",
                    (
                        TASK_ID,
                        "error",
                        f"Erro: {str(e)} (tentativa {failure_count})",
                    ),
                )
            )
        finally:
            wait_for_interval_with_backoff(
                stop_event, "file reader task", failure_count
            )

    # Task is stopping, send final status
    logger.info("File reader task stopping")
    queue.put(("TASK_STATUS", (TASK_ID, "stopped", "Tarefa finalizada")))


# Task 2: Process queued events into database
def task_db_processor(stop_event, queue):
    """
    Takes raw events from the queue and processes them into the database.
    This task handles all database insertion operations.
    """
    TASK_ID = "db_processor"

    logger.info("Starting database processor task")
    failure_count = 0

    # Send initial status
    queue.put(
        (
            "TASK_STATUS",
            (TASK_ID, "start", "Iniciando processador de banco de dados..."),
        )
    )

    # Initial waiting state
    queue.put(
        (
            "TASK_STATUS",
            (
                TASK_ID,
                "waiting",
                "Aguardando novos eventos para processar...",
            ),
        )
    )

    while not stop_event.is_set():
        try:
            # Check for queued events to process
            try:
                message_type, data = queue.get(timeout=1)  # Wait 1 second for new data

                if message_type == "PROCESS_EVENTS":
                    logger.debug(f"Processing {len(data)} events into database")
                    # Update status when starting to process new events
                    queue.put(
                        (
                            "TASK_STATUS",
                            (
                                TASK_ID,
                                "running",
                                f"Processando {len(data)} eventos no banco...",
                            ),
                        )
                    )

                    try:
                        # Check cancellation before processing
                        check_cancellation_frequently(stop_event, "db processor", 0.05)

                        processed_records = process_events_to_database(data, stop_event)

                        # Check cancellation after processing
                        check_cancellation_frequently(stop_event, "db processor", 0.05)

                        if processed_records:
                            logger.info(
                                f"Successfully processed {len(processed_records)} records into database"
                            )

                            # Notify GUI about new processed records
                            queue.put(("DATA_PROCESSED", len(processed_records)))

                            queue.put(
                                (
                                    "TASK_STATUS",
                                    (
                                        TASK_ID,
                                        "success",
                                        f"Processados {len(processed_records)} registros. Aguardando novos eventos...",
                                    ),
                                )
                            )
                        else:
                            queue.put(
                                (
                                    "TASK_STATUS",
                                    (
                                        TASK_ID,
                                        "warning",
                                        "Nenhum registro processado. Aguardando novos eventos...",
                                    ),
                                )
                            )

                        # After processing, go back to waiting state
                        queue.put(
                            (
                                "TASK_STATUS",
                                (
                                    TASK_ID,
                                    "waiting",
                                    "Aguardando novos eventos para processar...",
                                ),
                            )
                        )
                        # Reset failure count on successful processing
                        failure_count = 0
                    except InterruptedError:
                        logger.info("Database processor task cancelled")
                        queue.put(
                            (
                                "TASK_STATUS",
                                (
                                    TASK_ID,
                                    "cancelled",
                                    "Processamento cancelado",
                                ),
                            )
                        )
                        break

            except Empty:
                # No new data, continue loop - status remains in waiting state
                continue

        except InterruptedError:
            # Handle cancellation gracefully
            logger.info("Database processor task cancelled")
            queue.put(("TASK_STATUS", (TASK_ID, "cancelled", "Tarefa cancelada")))
            break
        except Exception as e:
            failure_count += 1
            logger.warning(f"Error in database processor task: {e}")
            logger.exception(e)
            queue.put(("TASK_STATUS", (TASK_ID, "error", f"Erro: {str(e)}")))
        finally:
            # Short pause to prevent busy waiting
            if not stop_event.is_set():
                stop_event.wait(0.1)

    # Task is stopping, send final status
    logger.info("Database processor task stopping")
    queue.put(("TASK_STATUS", (TASK_ID, "stopped", "Tarefa finalizada")))


# Task 3: Sync unsynced DB records to API
def task_db_sync(stop_event, queue):
    """
    Fetches unsynced transactions from the DB and pushes them to the API.
    This task only handles API synchronization with exponential backoff for network issues.
    """
    TASK_ID = "db_sync"

    logger.info("Starting DB sync task")
    failure_count = 0

    # Send initial start status
    queue.put(
        (
            "TASK_STATUS",
            (TASK_ID, "start", "Iniciando sincronizador de banco..."),
        )
    )

    while not stop_event.is_set():
        try:
            # Check cancellation at start of each cycle
            check_cancellation_frequently(stop_event, TASK_ID, 0.05)

            # Logger debug
            logger.debug("DB sync task cycle starting")

            # Send initial start status for this cycle
            queue.put(
                (
                    "TASK_STATUS",
                    (TASK_ID, "start", "Iniciando ciclo de sincronização..."),
                )
            )

            # Optionally, fetch and sync students if needed
            logger.debug("Fetching and syncing students")
            queue.put(
                (
                    "TASK_STATUS",
                    (TASK_ID, "running", "Sincronizando dados de estudantes..."),
                )
            )

            try:
                fetch_and_sync_students()
            except Exception as sync_error:
                logger.warning(f"Error syncing students: {sync_error}")
                # Continue with access sync even if student sync fails

            # Check cancellation after student sync
            check_cancellation_frequently(stop_event, "db sync", 0.05)

            logger.debug("Fetching not synced access records")
            queue.put(
                (
                    "TASK_STATUS",
                    (TASK_ID, "running", "Buscando registros não sincronizados..."),
                )
            )

            # Get cutoff date and filter directly in database for better performance
            cutoff = datetime.strptime(get_cutoff(), "%d/%m/%Y").date()
            acessos = Acesso.get_unsynced(cutoff_date=cutoff)
            logger.info(
                f"Found {len(acessos)} unsynced access records after cutoff date {cutoff}"
            )

            if acessos:
                # Check cancellation before API operations
                check_cancellation_frequently(stop_event, "db sync", 0.05)

                logger.debug("Posting access records to API and updating synced status")
                queue.put(
                    (
                        "TASK_STATUS",
                        (
                            TASK_ID,
                            "running",
                            f"Enviando {len(acessos)} registros para API...",
                        ),
                    )
                )

                try:
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
                                    TASK_ID,
                                    "success",
                                    f"Sincronizados {len(results)} registros com sucesso",
                                ),
                            )
                        )
                        # Reset failure count on successful sync
                        failure_count = 0
                    else:
                        queue.put(
                            (
                                "TASK_STATUS",
                                (
                                    TASK_ID,
                                    "warning",
                                    "Nenhum registro foi sincronizado",
                                ),
                            )
                        )
                        # Reset failure count even if no records were synced (not a failure)
                        failure_count = 0
                except Exception as api_error:
                    logger.error(f"Error during API sync: {api_error}")
                    # Update status to show error occurred, but don't raise yet
                    queue.put(
                        (
                            "TASK_STATUS",
                            (
                                TASK_ID,
                                "error",
                                f"Erro durante sincronização: {str(api_error)[:50]}...",
                            ),
                        )
                    )
                    raise  # Re-raise to be caught by outer exception handler
            else:
                queue.put(
                    (
                        "TASK_STATUS",
                        (
                            TASK_ID,
                            "success",
                            "Sincronização concluída - nenhum registro não sincronizado encontrado",
                        ),
                    )
                )
                # Reset failure count when no records to sync
                failure_count = 0

        except InterruptedError:
            # Handle cancellation gracefully
            logger.info("DB sync task cancelled")
            queue.put(
                ("TASK_STATUS", (TASK_ID, "cancelled", "Sincronização cancelada"))
            )
            break
        except Exception as e:
            failure_count += 1

            # Reduce logging frequency for repeated network failures
            if failure_count <= 3:
                logger.warning(f"Error in DB sync task (failure #{failure_count}): {e}")
                logger.exception(e)
            elif failure_count % 10 == 0:  # Log every 10th failure to track persistence
                logger.error(
                    f"DB sync task still failing after {failure_count} attempts: {e}"
                )
            else:
                logger.debug(f"DB sync task failure #{failure_count}: {e}")

            queue.put(
                (
                    "TASK_STATUS",
                    (TASK_ID, "error", f"Erro: {str(e)} (tentativa {failure_count})"),
                )
            )
        finally:
            wait_for_interval_with_backoff(stop_event, "DB sync task", failure_count)

            # Signal start of new cycle after the wait
            if not stop_event.is_set():
                queue.put(
                    (
                        "TASK_STATUS",
                        (TASK_ID, "start", "Iniciando novo ciclo de sincronização..."),
                    )
                )

    # Task is stopping, send final status
    logger.info("DB sync task stopping")
    queue.put(("TASK_STATUS", (TASK_ID, "stopped", "Tarefa finalizada")))
