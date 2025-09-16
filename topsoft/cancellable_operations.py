"""
Módulo para gerenciar operações canceláveis com progress feedback.
Fornece classes base para operações longas que podem ser canceladas pelo usuário.
"""

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class OperationState(Enum):
    """Estados possíveis de uma operação cancelável."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ProgressInfo:
    """Informações de progresso de uma operação."""

    current: int
    total: int
    message: str = ""
    percentage: float = 0.0

    def __post_init__(self):
        if self.total > 0:
            self.percentage = (self.current / self.total) * 100


class CancellableOperation(ABC):
    """
    Classe base para operações que podem ser canceladas.

    Fornece funcionalidade de cancelamento, progresso e callbacks para UI.
    """

    def __init__(self, name: str = "Operation"):
        self.name = name
        self.state = OperationState.IDLE
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Callbacks para atualização da UI
        self._progress_callback: Optional[Callable[[ProgressInfo], None]] = None
        self._state_callback: Optional[Callable[[OperationState], None]] = None
        self._completion_callback: Optional[
            Callable[[bool, Optional[Exception]], None]
        ] = None

        # Controle de progresso
        self._current_progress = 0
        self._total_progress = 0
        self._progress_message = ""

    def set_progress_callback(self, callback: Callable[[ProgressInfo], None]):
        """Define callback para atualizações de progresso."""
        self._progress_callback = callback

    def set_state_callback(self, callback: Callable[[OperationState], None]):
        """Define callback para mudanças de estado."""
        self._state_callback = callback

    def set_completion_callback(
        self, callback: Callable[[bool, Optional[Exception]], None]
    ):
        """Define callback para conclusão da operação."""
        self._completion_callback = callback

    def start(self) -> bool:
        """
        Inicia a operação em uma thread separada.

        Returns:
            bool: True se a operação foi iniciada com sucesso, False caso contrário.
        """
        if self.state != OperationState.IDLE:
            logger.warning(
                f"Cannot start operation {self.name} - current state: {self.state}"
            )
            return False

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_operation, daemon=True)
        self._thread.start()
        return True

    def cancel(self) -> bool:
        """
        Cancela a operação em execução.

        Returns:
            bool: True se o cancelamento foi solicitado com sucesso.
        """
        if self.state not in [OperationState.RUNNING, OperationState.PAUSED]:
            return False

        logger.info(f"Cancelling operation: {self.name}")
        self._stop_event.set()
        self._set_state(OperationState.CANCELLED)
        return True

    def is_running(self) -> bool:
        """Verifica se a operação está em execução."""
        return self.state == OperationState.RUNNING

    def is_cancelled(self) -> bool:
        """Verifica se a operação foi cancelada."""
        return self._stop_event.is_set()

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Aguarda a conclusão da operação.

        Args:
            timeout: Tempo limite em segundos para aguardar.

        Returns:
            bool: True se a operação foi concluída, False se timeout.
        """
        if self._thread is None:
            return True

        self._thread.join(timeout)
        return not self._thread.is_alive()

    def _run_operation(self):
        """Executa a operação com tratamento de erro e callbacks."""
        try:
            self._set_state(OperationState.RUNNING)
            logger.info(f"Starting operation: {self.name}")

            result = self.execute()

            if self.is_cancelled():
                logger.info(f"Operation cancelled: {self.name}")
                self._notify_completion(False, None)
            else:
                logger.info(f"Operation completed successfully: {self.name}")
                self._set_state(OperationState.COMPLETED)
                self._notify_completion(True, None)

        except Exception as e:
            logger.error(f"Operation failed: {self.name} - {e}")
            logger.exception(e)
            self._set_state(OperationState.ERROR)
            self._notify_completion(False, e)

    def _set_state(self, new_state: OperationState):
        """Atualiza o estado e notifica callbacks."""
        self.state = new_state
        if self._state_callback:
            try:
                self._state_callback(new_state)
            except Exception as e:
                logger.error(f"Error in state callback: {e}")

    def _update_progress(self, current: int, total: int, message: str = ""):
        """Atualiza o progresso e notifica callbacks."""
        self._current_progress = current
        self._total_progress = total
        self._progress_message = message

        if self._progress_callback:
            try:
                progress_info = ProgressInfo(current, total, message)
                self._progress_callback(progress_info)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    def _notify_completion(self, success: bool, error: Optional[Exception]):
        """Notifica a conclusão da operação."""
        if self._completion_callback:
            try:
                self._completion_callback(success, error)
            except Exception as e:
                logger.error(f"Error in completion callback: {e}")

    def _check_cancellation(self, interval: float = 0.1):
        """
        Verifica se a operação foi cancelada e levanta exceção se necessário.

        Args:
            interval: Intervalo mínimo entre verificações para evitar overhead.
        """
        if self.is_cancelled():
            raise OperationCancelledException(f"Operation {self.name} was cancelled")

        # Pequeno delay para permitir que a UI responda
        time.sleep(interval)

    @abstractmethod
    def execute(self) -> Any:
        """
        Método abstrato que deve ser implementado pelas subclasses.

        Deve conter a lógica principal da operação e chamar regularmente
        _check_cancellation() e _update_progress().

        Returns:
            Any: Resultado da operação.
        """
        pass


class OperationCancelledException(Exception):
    """Exceção lançada quando uma operação é cancelada."""

    pass


class BatchProcessor:
    """
    Utilitário para processar itens em lotes com suporte a cancelamento.
    """

    def __init__(self, operation: CancellableOperation, batch_size: int = 100):
        self.operation = operation
        self.batch_size = batch_size

    def process_items(
        self,
        items: list,
        processor_func: Callable,
        progress_message: str = "Processing",
    ):
        """
        Processa uma lista de itens em lotes com verificação de cancelamento.

        Args:
            items: Lista de itens para processar
            processor_func: Função que processa um item individual
            progress_message: Mensagem de progresso

        Returns:
            list: Lista de resultados processados
        """
        results = []
        total_items = len(items)

        for i in range(0, total_items, self.batch_size):
            # Verifica cancelamento antes de cada lote
            self.operation._check_cancellation()

            batch = items[i : i + self.batch_size]
            batch_number = (i // self.batch_size) + 1
            total_batches = (total_items + self.batch_size - 1) // self.batch_size

            # Atualiza progresso
            message = f"{progress_message} - Lote {batch_number}/{total_batches}"
            self.operation._update_progress(i, total_items, message)

            # Processa o lote
            for item in batch:
                try:
                    result = processor_func(item)
                    if result is not None:
                        results.append(result)
                except Exception as e:
                    logger.warning(f"Error processing item {item}: {e}")

                # Verifica cancelamento a cada item processado
                self.operation._check_cancellation(0.01)  # Verificação mais frequente

        # Progresso final
        self.operation._update_progress(
            total_items, total_items, f"{progress_message} - Concluído"
        )
        return results


class FileProcessor(BatchProcessor):
    """
    Processador especializado para arquivos grandes com leitura line-by-line.
    """

    def process_file(
        self,
        filepath: str,
        line_processor_func: Callable,
        encoding: str = "utf-8",
        progress_message: str = "Reading file",
    ):
        """
        Processa um arquivo linha por linha com verificação de cancelamento.

        Args:
            filepath: Caminho para o arquivo
            line_processor_func: Função que processa uma linha individual
            encoding: Codificação do arquivo
            progress_message: Mensagem de progresso

        Returns:
            list: Lista de resultados processados
        """
        results = []

        try:
            # Primeiro, conta o número total de linhas para progresso
            with open(filepath, "r", encoding=encoding) as file:
                total_lines = sum(1 for _ in file)

            # Agora processa o arquivo
            with open(filepath, "r", encoding=encoding) as file:
                for line_number, line in enumerate(file, 1):
                    # Verifica cancelamento a cada linha
                    self.operation._check_cancellation(0.01)

                    # Atualiza progresso a cada 100 linhas ou no final
                    if line_number % 100 == 0 or line_number == total_lines:
                        message = (
                            f"{progress_message} - Linha {line_number}/{total_lines}"
                        )
                        self.operation._update_progress(
                            line_number, total_lines, message
                        )

                    # Processa a linha
                    try:
                        result = line_processor_func(line.strip(), line_number)
                        if result is not None:
                            results.append(result)
                    except Exception as e:
                        logger.warning(f"Error processing line {line_number}: {e}")

        except OperationCancelledException:
            raise
        except Exception as e:
            logger.error(f"Error reading file {filepath}: {e}")
            raise

        return results
