import asyncio
import logging
import threading
import time
from datetime import datetime
from enum import Enum
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


class TaskState(Enum):
    """Enumeration of possible task states."""

    STARTING = "starting"
    RUNNING = "running"
    WAITING = "waiting"
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    CANCELLED = "cancelled"
    STOPPED = "stopped"


class BaseTask:
    """Base class for all tasks with thread-safe public attributes."""

    def __init__(self, task_id: str, name: str, description: str):
        self.task_id = task_id
        self.name = name
        self.description = description

        # Public attributes that can be read by UI (thread-safe)
        self._lock = threading.Lock()
        self.state = TaskState.STARTING
        self.details = "Iniciando tarefa..."
        self.last_run_time = None
        self.error_message = None
        self.failure_count = 0

        # Control attributes
        self.stop_event = None
        self.queue = None
        self.thread = None

    def update_state(self, state: TaskState, details: str = "", update_time: bool = True):
        """Update task state in a thread-safe manner."""
        with self._lock:
            self.state = state
            self.details = details
            if update_time and state in [TaskState.RUNNING, TaskState.SUCCESS]:
                self.last_run_time = datetime.now()
            if state != TaskState.ERROR:
                self.error_message = None

    def set_error(self, error_message: str):
        """Set error state with message."""
        with self._lock:
            self.state = TaskState.ERROR
            self.error_message = error_message
            self.details = f"Erro: {error_message}"

    def start(self, stop_event, queue):
        """Start the task in a separate thread."""
        self.stop_event = stop_event
        self.queue = queue
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        return self.thread

    def run(self):
        """Main task execution - to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement run method")

    def check_cancellation(self, check_interval=0.1):
        """Check if task should be cancelled."""
        if self.stop_event and self.stop_event.is_set():
            logger.info(f"Task {self.task_id} cancelled by user request")
            raise InterruptedError(f"Task {self.task_id} was cancelled")

        # Small sleep to allow other threads to run
        if self.stop_event:
            self.stop_event.wait(check_interval)


class FileReaderTask(BaseTask):
    """
    Reads the bilhetes file as fast as possible, detects new transactions, and queues them for DB insertion.
    This task only reads the file and queues raw data - no database operations.
    """

    def __init__(self):
        super().__init__(
            "file_reader",
            "📄 Leitor de Arquivo",
            "Lê novos dados do arquivo bilhetes.txt",
        )

    def run(self):
        logger.info(f"Starting {self.name}")
        self.failure_count = 0

        while not self.stop_event.is_set():
            try:
                self.check_cancellation(0.05)
                logger.debug("File reader task cycle starting")

                self.update_state(TaskState.STARTING, "Iniciando leitor de arquivos...")

                bilhetes_path = get_bilhetes_path()
                if not bilhetes_path or bilhetes_path == "":
                    raise FileNotFoundError("Caminho dos bilhetes não configurado")

                self.check_cancellation(0.05)

                logger.debug(f'Fast reading bilhetes from "{bilhetes_path}"')
                self.update_state(TaskState.RUNNING, f"Lendo arquivo: {bilhetes_path}")

                new_events = read_bilhetes_fast(bilhetes_path, self.stop_event)

                self.check_cancellation(0.05)

                if new_events:
                    logger.info(f"Found {len(new_events)} new events, queueing for processing")
                    self.queue.put(("PROCESS_EVENTS", new_events))
                    self.update_state(
                        TaskState.SUCCESS,
                        f"Encontrados {len(new_events)} novos eventos",
                    )
                    self.failure_count = 0
                else:
                    self.update_state(TaskState.SUCCESS, "Nenhum novo evento encontrado")
                    self.failure_count = 0

            except InterruptedError:
                logger.info("File reader task cancelled")
                self.update_state(TaskState.CANCELLED, "Tarefa cancelada")
                break
            except Exception as e:
                self.failure_count += 1
                logger.warning(f"Error in file reader task (failure #{self.failure_count}): {e}")
                if self.failure_count <= 3:
                    logger.exception(e)
                self.set_error(f"{str(e)} (tentativa {self.failure_count})")
            finally:
                wait_for_interval_with_backoff(self.stop_event, "file reader task", self.failure_count)

        logger.info("File reader task stopping")
        self.update_state(TaskState.STOPPED, "Tarefa finalizada")


class DatabaseProcessorTask(BaseTask):
    """
    Takes raw events from the queue and processes them into the database.
    This task handles all database insertion operations.
    """

    def __init__(self):
        super().__init__(
            "db_processor",
            "🗄️ Processador de Banco",
            "Processa eventos na base de dados",
        )

    def run(self):
        logger.info(f"Starting {self.name}")
        self.failure_count = 0

        self.update_state(TaskState.STARTING, "Iniciando processador de banco de dados...")
        self.update_state(TaskState.WAITING, "Aguardando novos eventos para processar...")

        while not self.stop_event.is_set():
            try:
                try:
                    message_type, data = self.queue.get(timeout=1)

                    if message_type == "PROCESS_EVENTS":
                        logger.debug(f"Processing {len(data)} events into database")
                        self.update_state(
                            TaskState.RUNNING,
                            f"Processando {len(data)} eventos no banco...",
                        )

                        try:
                            self.check_cancellation(0.05)
                            processed_records = process_events_to_database(data, self.stop_event)
                            self.check_cancellation(0.05)

                            if processed_records:
                                logger.info(f"Successfully processed {len(processed_records)} records into database")
                                self.queue.put(("DATA_PROCESSED", len(processed_records)))
                                self.update_state(
                                    TaskState.SUCCESS,
                                    f"Processados {len(processed_records)} registros. Aguardando novos eventos...",
                                )
                            else:
                                self.update_state(
                                    TaskState.WARNING,
                                    "Nenhum registro processado. Aguardando novos eventos...",
                                )

                            self.update_state(
                                TaskState.WAITING,
                                "Aguardando novos eventos para processar...",
                            )
                            self.failure_count = 0

                        except InterruptedError:
                            logger.info("Database processor task cancelled")
                            self.update_state(TaskState.CANCELLED, "Processamento cancelado")
                            break

                except Empty:
                    continue

            except InterruptedError:
                logger.info("Database processor task cancelled")
                self.update_state(TaskState.CANCELLED, "Tarefa cancelada")
                break
            except Exception as e:
                self.failure_count += 1
                logger.warning(f"Error in database processor task: {e}")
                logger.exception(e)
                self.set_error(str(e))
            finally:
                if not self.stop_event.is_set():
                    self.stop_event.wait(0.1)

        logger.info("Database processor task stopping")
        self.update_state(TaskState.STOPPED, "Tarefa finalizada")


class DatabaseSyncTask(BaseTask):
    """
    Fetches unsynced transactions from the DB and pushes them to the API.
    This task only handles API synchronization with exponential backoff for network issues.
    """

    def __init__(self):
        super().__init__("db_sync", "🔄 Sincronização API", "Sincroniza registros com ActivitySoft")

    def run(self):
        logger.info(f"Starting {self.name}")
        self.failure_count = 0

        self.update_state(TaskState.STARTING, "Iniciando sincronizador de banco...")

        while not self.stop_event.is_set():
            try:
                self.check_cancellation(0.05)
                logger.debug("DB sync task cycle starting")

                self.update_state(TaskState.STARTING, "Iniciando ciclo de sincronização...")

                logger.debug("Fetching and syncing students")
                self.update_state(TaskState.RUNNING, "Sincronizando dados de estudantes...")

                try:
                    fetch_and_sync_students()
                except Exception as sync_error:
                    logger.warning(f"Error syncing students: {sync_error}")

                self.check_cancellation(0.05)

                logger.debug("Fetching not synced access records")
                self.update_state(TaskState.RUNNING, "Buscando registros não sincronizados...")

                cutoff = datetime.strptime(get_cutoff(), "%d/%m/%Y").date()
                acessos = Acesso.get_unsynced(cutoff_date=cutoff)
                logger.info(f"Found {len(acessos)} unsynced access records after cutoff date {cutoff}")

                if acessos:
                    self.check_cancellation(0.05)

                    logger.debug("Posting access records to API and updating synced status")
                    self.update_state(
                        TaskState.RUNNING,
                        f"Enviando {len(acessos)} registros para API...",
                    )

                    try:
                        results = asyncio.run(post_acessos_and_update_synced_status(acessos))

                        if results:
                            self.queue.put(("SYNC_COMPLETED", [acesso.id for acesso in results]))
                            logger.debug(f"Put {len(results)} synced access records into the queue")
                            self.update_state(
                                TaskState.SUCCESS,
                                f"Sincronizados {len(results)} registros com sucesso",
                            )
                            self.failure_count = 0
                        else:
                            self.update_state(TaskState.WARNING, "Nenhum registro foi sincronizado")
                            self.failure_count = 0

                    except Exception as api_error:
                        logger.error(f"Error during API sync: {api_error}")
                        self.set_error(f"Erro durante sincronização: {str(api_error)[:50]}...")
                        raise
                else:
                    self.update_state(
                        TaskState.SUCCESS,
                        "Sincronização concluída - nenhum registro não sincronizado encontrado",
                    )
                    self.failure_count = 0

            except InterruptedError:
                logger.info("DB sync task cancelled")
                self.update_state(TaskState.CANCELLED, "Sincronização cancelada")
                break
            except Exception as e:
                self.failure_count += 1

                if self.failure_count <= 3:
                    logger.warning(f"Error in DB sync task (failure #{self.failure_count}): {e}")
                    logger.exception(e)
                elif self.failure_count % 10 == 0:
                    logger.error(f"DB sync task still failing after {self.failure_count} attempts: {e}")
                else:
                    logger.debug(f"DB sync task failure #{self.failure_count}: {e}")

                self.set_error(f"{str(e)} (tentativa {self.failure_count})")
            finally:
                wait_for_interval_with_backoff(self.stop_event, "DB sync task", self.failure_count)

                if not self.stop_event.is_set():
                    self.update_state(TaskState.STARTING, "Iniciando novo ciclo de sincronização...")

        logger.info("DB sync task stopping")
        self.update_state(TaskState.STOPPED, "Tarefa finalizada")
