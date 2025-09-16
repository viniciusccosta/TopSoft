"""
Diálogos de progresso com suporte a cancelamento.
Fornece interfaces visuais para operações longas que podem ser canceladas.
"""

import logging
import threading
from tkinter import messagebox
from typing import Optional

import ttkbootstrap as ttk

from topsoft.cancellable_operations import (
    CancellableOperation,
    OperationState,
    ProgressInfo,
)

logger = logging.getLogger(__name__)


class ProgressDialog:
    """
    Diálogo modal que mostra o progresso de uma operação cancelável.

    Características:
    - Barra de progresso animada
    - Botão de cancelamento
    - Mensagens de status atualizadas
    - Modal (bloqueia a janela pai)
    - Auto-fechamento quando operação completa
    """

    def __init__(
        self,
        parent,
        title: str = "Processando...",
        allow_cancel: bool = True,
        width: int = 400,
        height: int = 150,
    ):
        self.parent = parent
        self.title = title
        self.allow_cancel = allow_cancel
        self.operation: Optional[CancellableOperation] = None
        self.result_callback = None
        self.auto_close = True

        # Criar janela modal
        self.window = ttk.Toplevel(parent)
        self.window.title(title)
        self.window.geometry(f"{width}x{height}")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()  # Modal

        # Centralizar na tela
        self._center_window()

        # Prevenir fechamento direto da janela
        self.window.protocol("WM_DELETE_WINDOW", self._on_window_close)

        self._setup_ui()

    def _center_window(self):
        """Centraliza a janela na tela."""
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (self.window.winfo_width() // 2)
        y = (self.window.winfo_screenheight() // 2) - (self.window.winfo_height() // 2)
        self.window.geometry(f"+{x}+{y}")

    def _setup_ui(self):
        """Configura a interface do diálogo."""
        # Frame principal com padding
        main_frame = ttk.Frame(self.window, padding=20)
        main_frame.pack(fill="both", expand=True)

        # Label de status
        self.status_label = ttk.Label(
            main_frame, text="Iniciando operação...", font=("Arial", 10), wraplength=350
        )
        self.status_label.pack(pady=(0, 15))

        # Barra de progresso
        self.progress_var = ttk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            main_frame,
            variable=self.progress_var,
            mode="determinate",
            length=350,
            height=20,
        )
        self.progress_bar.pack(pady=(0, 10))

        # Label de percentual
        self.percent_label = ttk.Label(
            main_frame, text="0%", font=("Arial", 9), foreground="gray"
        )
        self.percent_label.pack(pady=(0, 15))

        # Frame para botões
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x")

        # Botão cancelar
        if self.allow_cancel:
            self.cancel_button = ttk.Button(
                button_frame,
                text="Cancelar",
                command=self._on_cancel,
                bootstyle="danger-outline",
                width=12,
            )
            self.cancel_button.pack(side="right")

        # Botão OK (inicialmente oculto)
        self.ok_button = ttk.Button(
            button_frame, text="OK", command=self._on_ok, bootstyle="primary", width=12
        )

    def set_result_callback(self, callback):
        """Define callback chamado quando operação termina."""
        self.result_callback = callback

    def set_auto_close(self, auto_close: bool):
        """Define se o diálogo deve fechar automaticamente ao completar."""
        self.auto_close = auto_close

    def run_operation(self, operation: CancellableOperation) -> bool:
        """
        Executa uma operação mostrando progresso.

        Args:
            operation: Operação a ser executada

        Returns:
            bool: True se operação foi concluída com sucesso, False se cancelada
        """
        self.operation = operation

        # Configurar callbacks
        operation.set_progress_callback(self._on_progress_update)
        operation.set_state_callback(self._on_state_change)
        operation.set_completion_callback(self._on_completion)

        # Iniciar operação
        if not operation.start():
            messagebox.showerror("Erro", "Não foi possível iniciar a operação.")
            self._close()
            return False

        # Iniciar animação de progresso indeterminado
        self.progress_bar.config(mode="indeterminate")
        self.progress_bar.start()

        # Manter janela responsiva
        self._keep_responsive()

        return True

    def _keep_responsive(self):
        """Mantém a janela responsiva durante a operação."""
        if self.operation and self.operation.is_running():
            self.window.after(100, self._keep_responsive)

    def _on_progress_update(self, progress: ProgressInfo):
        """Callback chamado quando progresso é atualizado."""

        def update_ui():
            if self.window.winfo_exists():
                # Atualizar mensagem
                if progress.message:
                    self.status_label.config(text=progress.message)

                # Atualizar barra de progresso
                if progress.total > 0:
                    self.progress_bar.config(mode="determinate")
                    self.progress_bar.stop()
                    self.progress_var.set(progress.percentage)
                    self.percent_label.config(text=f"{progress.percentage:.1f}%")
                else:
                    # Progresso indeterminado
                    if self.progress_bar.cget("mode") != "indeterminate":
                        self.progress_bar.config(mode="indeterminate")
                        self.progress_bar.start()
                    self.percent_label.config(text="")

        # Agendar atualização na thread principal
        self.window.after(0, update_ui)

    def _on_state_change(self, state: OperationState):
        """Callback chamado quando estado da operação muda."""

        def update_ui():
            if not self.window.winfo_exists():
                return

            if state == OperationState.RUNNING:
                self.status_label.config(text="Operação em andamento...")
                if self.allow_cancel:
                    self.cancel_button.config(state="normal")

            elif state == OperationState.CANCELLED:
                self.progress_bar.stop()
                self.progress_bar.config(mode="determinate")
                self.progress_var.set(0)
                self.status_label.config(text="Operação cancelada pelo usuário.")
                self.percent_label.config(text="Cancelado")
                if self.allow_cancel:
                    self.cancel_button.config(state="disabled")
                self._show_ok_button()

            elif state == OperationState.ERROR:
                self.progress_bar.stop()
                self.progress_bar.config(mode="determinate", bootstyle="danger")
                self.status_label.config(text="Erro durante a operação.")
                self.percent_label.config(text="Erro")
                if self.allow_cancel:
                    self.cancel_button.config(state="disabled")
                self._show_ok_button()

            elif state == OperationState.COMPLETED:
                self.progress_bar.stop()
                self.progress_bar.config(mode="determinate", bootstyle="success")
                self.progress_var.set(100)
                self.status_label.config(text="Operação concluída com sucesso!")
                self.percent_label.config(text="100%")
                if self.allow_cancel:
                    self.cancel_button.config(state="disabled")

                if self.auto_close:
                    # Fechar automaticamente após 1 segundo
                    self.window.after(1000, self._close)
                else:
                    self._show_ok_button()

        # Agendar atualização na thread principal
        self.window.after(0, update_ui)

    def _on_completion(self, success: bool, error: Optional[Exception]):
        """Callback chamado quando operação termina."""

        def handle_completion():
            if self.result_callback:
                try:
                    self.result_callback(success, error)
                except Exception as e:
                    logger.error(f"Error in result callback: {e}")

            if not success and error and not self.auto_close:
                # Mostrar erro se não for auto-close
                error_msg = str(error) if error else "Erro desconhecido"
                messagebox.showerror("Erro na Operação", error_msg)

        # Agendar na thread principal
        self.window.after(0, handle_completion)

    def _show_ok_button(self):
        """Mostra o botão OK e esconde o botão cancelar."""
        if self.allow_cancel:
            self.cancel_button.pack_forget()
        self.ok_button.pack(side="right")

    def _on_cancel(self):
        """Callback do botão cancelar."""
        if self.operation:
            # Desabilitar botão para evitar múltiplos cliques
            self.cancel_button.config(state="disabled")
            self.status_label.config(text="Cancelando operação...")

            # Cancelar operação
            if self.operation.cancel():
                logger.info("User requested operation cancellation")
            else:
                logger.warning("Could not cancel operation")
                self.cancel_button.config(state="normal")

    def _on_ok(self):
        """Callback do botão OK."""
        self._close()

    def _on_window_close(self):
        """Callback quando usuário tenta fechar janela."""
        if self.operation and self.operation.is_running():
            # Se operação está rodando, tratar como cancelamento
            result = messagebox.askyesno(
                "Cancelar Operação",
                "Uma operação está em andamento. Deseja cancelá-la?",
                parent=self.window,
            )
            if result:
                self._on_cancel()
        else:
            # Operação não está rodando, pode fechar
            self._close()

    def _close(self):
        """Fecha o diálogo."""
        try:
            if self.window.winfo_exists():
                self.window.grab_release()
                self.window.destroy()
        except Exception as e:
            logger.error(f"Error closing progress dialog: {e}")


def show_progress_dialog(
    parent,
    operation: CancellableOperation,
    title: str = "Processando...",
    allow_cancel: bool = True,
    auto_close: bool = True,
) -> bool:
    """
    Função utilitária para mostrar um diálogo de progresso.

    Args:
        parent: Janela pai
        operation: Operação a ser executada
        title: Título do diálogo
        allow_cancel: Se permite cancelamento
        auto_close: Se fecha automaticamente ao completar

    Returns:
        bool: True se operação foi concluída com sucesso
    """
    dialog = ProgressDialog(parent, title, allow_cancel)
    dialog.set_auto_close(auto_close)

    # Variável para capturar resultado
    result = {"success": False}

    def on_result(success, error):
        result["success"] = success

    dialog.set_result_callback(on_result)
    dialog.run_operation(operation)

    # Aguardar fechamento do diálogo
    try:
        dialog.window.wait_window()
    except:
        pass

    return result["success"]
