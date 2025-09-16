import logging
import threading
from datetime import datetime
from time import sleep
from tkinter import Frame, Menu, filedialog

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.tableview import Tableview

from topsoft.card_operations import ExportCartoesOperation, ImportCartoesOperation
from topsoft.constants import DEFAULT_INTERVAL, MAX_INTERVAL, MIN_INTERVAL
from topsoft.models import Acesso, Aluno, CartaoAcesso
from topsoft.progress_dialog import show_progress_dialog
from topsoft.repository import (
    bind_matricula_to_cartao_acesso_v2 as bind_matricula_to_cartao_acesso,
)
from topsoft.secrets import get_api_key, set_api_key
from topsoft.settings import (
    get_bilhetes_path,
    get_cutoff,
    get_interval,
    set_bilhetes_path,
    set_cutoff,
    set_interval,
)
from topsoft.tasks import TaskState

logger = logging.getLogger(__name__)


class StudentSelectionDialog:
    """
    Enhanced dialog for selecting a student with search functionality and table view.
    Can also be used for creating new access cards.
    """

    def __init__(
        self,
        parent,
        cartao_numeracao=None,
        current_aluno_info=None,
        callback=None,
        mode="bind",
    ):
        self.parent = parent
        self.cartao_numeracao = cartao_numeracao
        self.current_aluno_info = current_aluno_info
        self.callback = callback
        self.mode = (
            mode  # "bind" for existing card binding, "create" for new card creation
        )
        self.selected_aluno = None
        self.all_alunos = []
        self.filtered_alunos = []
        self.search_after_id = None  # For debouncing search

        self._create_dialog()
        self._load_students()

    def _create_dialog(self):
        """Create the dialog window and widgets."""
        if self.mode == "create":
            title = "Criar Novo Cartão de Acesso"
        else:
            title = "Selecionar Aluno para Vinculação"

        self.dialog = ttk.Toplevel(self.parent)
        self.dialog.title(title)
        # self.dialog.geometry(f"700x{dialog_height}")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()  # Make it modal

        # Main container
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(expand=True, fill="both", padx=20, pady=20)

        # Create appropriate header based on mode
        if self.mode == "create":
            self._create_new_card_header(main_frame)
        else:
            self._create_binding_header(main_frame)

        # Common components
        self._create_search_section(main_frame)
        self._create_table_section(main_frame)
        self._create_button_section(main_frame)

        # Keyboard shortcuts
        self.dialog.bind("<Escape>", lambda e: self._cancel())
        self.dialog.bind("<Control-f>", lambda e: self.search_entry.focus())

    def _create_binding_header(self, main_frame):
        """Create header for binding mode."""
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 20))

        ttk.Label(
            header_frame,
            text=f"Cartão de Acesso: {self.cartao_numeracao}",
            font=("Arial", 12, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            header_frame,
            text=f"Vinculação atual: {self.current_aluno_info}",
            font=("Arial", 10),
            foreground="gray",
        ).pack(anchor="w")

        # Instructions
        instructions_frame = ttk.Frame(header_frame)
        instructions_frame.pack(fill="x", pady=(10, 0))

        ttk.Label(
            instructions_frame, text="📋 Instruções:", font=("Arial", 9, "bold")
        ).pack(anchor="w")

        ttk.Label(
            instructions_frame,
            text="• Para vincular: busque e selecione um aluno abaixo",
            font=("Arial", 8),
            foreground="gray",
        ).pack(anchor="w", padx=(10, 0))

        ttk.Label(
            instructions_frame,
            text="• Para remover: clique em 'Remover Vinculação'",
            font=("Arial", 8),
            foreground="gray",
        ).pack(anchor="w", padx=(10, 0))

    def _create_new_card_header(self, main_frame):
        """Create header for new card creation mode."""
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 20))

        ttk.Label(
            header_frame,
            text="🆕 Criar Novo Cartão de Acesso",
            font=("Arial", 14, "bold"),
            foreground="green",
        ).pack(anchor="w")

        # Card number input
        card_input_frame = ttk.LabelFrame(
            header_frame, text="Número do Cartão", padding=10
        )
        card_input_frame.pack(fill="x", pady=(10, 0))

        input_frame = ttk.Frame(card_input_frame)
        input_frame.pack(fill="x")

        ttk.Label(input_frame, text="Digite o número do cartão:").pack(anchor="w")

        ttk.Label(
            input_frame,
            text="💡 Formato aceito: até 16 dígitos (zeros à esquerda serão adicionados automaticamente)",
            font=("Arial", 8),
            foreground="gray",
        ).pack(anchor="w")

        entry_frame = ttk.Frame(input_frame)
        entry_frame.pack(fill="x", pady=(5, 0))

        self.card_number_var = ttk.StringVar()
        self.card_number_entry = ttk.Entry(
            entry_frame,
            textvariable=self.card_number_var,
            font=("Arial", 12),
            bootstyle="success",
            width=20,
        )
        self.card_number_entry.pack(side="left")
        self.card_number_entry.focus()  # Focus on card number entry
        self.card_number_entry.bind("<Return>", lambda e: self._validate_card_number())

        # Validation button
        self.validate_button = ttk.Button(
            entry_frame,
            text="✓ Validar",
            command=self._validate_card_number,
            bootstyle="info-outline",
        )
        self.validate_button.pack(side="left", padx=(10, 0))

        # Status label
        self.card_status_label = ttk.Label(
            input_frame,
            text="Digite o número do cartão e clique em 'Validar'",
            font=("Arial", 9),
            foreground="gray",
        )
        self.card_status_label.pack(anchor="w", pady=(5, 0))

        # Instructions
        instructions_frame = ttk.Frame(header_frame)
        instructions_frame.pack(fill="x", pady=(10, 0))

        ttk.Label(
            instructions_frame, text="📋 Instruções:", font=("Arial", 9, "bold")
        ).pack(anchor="w")

        ttk.Label(
            instructions_frame,
            text="1. Digite o número do cartão e valide",
            font=("Arial", 8),
            foreground="gray",
        ).pack(anchor="w", padx=(10, 0))

        ttk.Label(
            instructions_frame,
            text="2. Busque e selecione um aluno para vincular (opcional)",
            font=("Arial", 8),
            foreground="gray",
        ).pack(anchor="w", padx=(10, 0))

        ttk.Label(
            instructions_frame,
            text="3. Clique em 'Criar Cartão' (pode criar sem vinculação)",
            font=("Arial", 8),
            foreground="gray",
        ).pack(anchor="w", padx=(10, 0))

    def _create_search_section(self, main_frame):
        """Create the search section."""
        # Search frame
        search_frame = ttk.LabelFrame(main_frame, text="Buscar Aluno", padding=10)
        search_frame.pack(fill="x", pady=(0, 10))

        # Search entry
        search_entry_frame = ttk.Frame(search_frame)
        search_entry_frame.pack(fill="x")

        ttk.Label(search_entry_frame, text="Buscar por nome ou matrícula:").pack(
            anchor="w"
        )

        # Tips label
        tip_text = "💡 Dica: Digite algumas letras do nome ou a matrícula completa"
        if self.mode == "create":
            tip_text += " (opcional - pode criar cartão sem vinculação)"

        ttk.Label(
            search_entry_frame,
            text=tip_text,
            font=("Arial", 8),
            foreground="gray",
        ).pack(anchor="w")

        self.search_var = ttk.StringVar()
        self.search_var.trace("w", self._on_search_changed)

        # Search entry with better styling
        search_input_frame = ttk.Frame(search_entry_frame)
        search_input_frame.pack(fill="x", pady=(5, 0))

        self.search_entry = ttk.Entry(
            search_input_frame,
            textvariable=self.search_var,
            font=("Arial", 11),
            bootstyle="info",
        )
        self.search_entry.pack(side="left", fill="x", expand=True)

        # Focus on search entry only if not in create mode
        if self.mode != "create":
            self.search_entry.focus()

        # Search info label
        search_info = ttk.Label(search_input_frame, text=" 🔍", font=("Arial", 12))
        search_info.pack(side="right", padx=(5, 0))

        # Clear search button
        clear_frame = ttk.Frame(search_frame)
        clear_frame.pack(fill="x", pady=(5, 0))

        ttk.Button(
            clear_frame,
            text="🔍 Limpar Busca",
            command=self._clear_search,
            bootstyle="outline",
        ).pack(side="left")

        self.results_label = ttk.Label(
            clear_frame, text="", font=("Arial", 9), foreground="gray"
        )
        self.results_label.pack(side="right")

    def _create_table_section(self, main_frame):
        """Create the table section."""
        # Table frame
        table_frame = ttk.LabelFrame(main_frame, text="Alunos Encontrados", padding=10)
        table_frame.pack(expand=True, fill="both", pady=(0, 10))

        # Create table
        columns = [
            {"text": "Matrícula", "stretch": False, "width": 100},
            {"text": "Nome", "stretch": True},
            {"text": "Curso", "stretch": False, "width": 150},
        ]

        self.table = Tableview(
            table_frame,
            coldata=columns,
            paginated=True,
            pagesize=15,
            searchable=False,  # We'll handle search ourselves
            autofit=True,
            autoalign=False,
            height=12,
        )
        self.table.pack(expand=True, fill="both")

        # Bind double-click to select
        self.table.view.bind("<Double-1>", self._on_table_double_click)
        self.table.view.bind("<Return>", self._on_table_enter)

    def _create_button_section(self, main_frame):
        """Create the button section based on mode."""
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))

        # Cancel button (always present)
        ttk.Button(
            button_frame, text="Cancelar", command=self._cancel, bootstyle="secondary"
        ).pack(side="left")

        if self.mode == "create":
            # Create card mode buttons
            ttk.Button(
                button_frame,
                text="🆕 Criar Cartão",
                command=self._create_new_card,
                bootstyle="success",
            ).pack(side="right")
        else:
            # Binding mode buttons
            # Make remove binding more prominent if there's a current binding
            remove_text = "🗑️ Remover Vinculação"
            if (
                self.current_aluno_info
                and "Não vinculado" not in self.current_aluno_info
            ):
                remove_bootstyle = "warning"
            else:
                remove_text = "Remover Vinculação (Já removido)"
                remove_bootstyle = "secondary"

            ttk.Button(
                button_frame,
                text=remove_text,
                command=self._remove_binding,
                bootstyle=remove_bootstyle,
            ).pack(side="left", padx=(10, 0))

            ttk.Button(
                button_frame,
                text="✅ Selecionar Aluno",
                command=self._select_student,
                bootstyle="success",
            ).pack(side="right")

    def _load_students(self):
        """Load all students in a background thread."""
        threading.Thread(target=self._load_students_thread, daemon=True).start()

    def _load_students_thread(self):
        """Background thread to load students."""
        try:
            # Load all students
            self.all_alunos = Aluno.get_all(sort_by="nome")

            # Update UI in main thread
            self.dialog.after(0, self._populate_table)

        except Exception as e:
            logger.error(f"Error loading students: {e}")
            self.dialog.after(
                0, lambda: self._show_error(f"Erro ao carregar alunos: {e}")
            )

    def _populate_table(self, students=None):
        """Populate the table with students."""
        if students is None:
            students = self.all_alunos

        self.filtered_alunos = students

        # Store current focus before clearing table
        focused_widget = self.dialog.focus_get()

        # Clear existing data
        self.table.delete_rows(indices=None, iids=None)

        # Add students to table
        for aluno in students:
            curso = getattr(aluno, "curso", "N/A") or "N/A"
            self.table.insert_row("end", (aluno.matricula, aluno.nome, curso))

        # Load table data
        self.table.load_table_data(clear_filters=True)

        # Restore focus to the search entry if it was focused before
        if focused_widget == self.search_entry:
            self.dialog.after_idle(lambda: self.search_entry.focus())

        # Update results label
        total_count = len(self.all_alunos)
        filtered_count = len(students)

        if total_count == filtered_count:
            self.results_label.config(text=f"{total_count} alunos")
        else:
            self.results_label.config(text=f"{filtered_count} de {total_count} alunos")

    def _on_search_changed(self, *args):
        """Handle search text changes with debouncing."""
        # Cancel previous search if it exists
        if self.search_after_id:
            self.dialog.after_cancel(self.search_after_id)

        # Schedule new search after a short delay (debouncing)
        self.search_after_id = self.dialog.after(300, self._perform_search)

    def _perform_search(self):
        """Actually perform the search."""
        search_text = self.search_var.get().lower().strip()

        if not search_text:
            # Show all students
            self._populate_table()
            return

        # Filter students by name or matricula
        filtered = []
        for aluno in self.all_alunos:
            name_match = search_text in aluno.nome.lower()
            matricula_match = search_text in str(aluno.matricula).lower()

            # Also check if search starts with any word in the name (for better matching)
            name_words = aluno.nome.lower().split()
            word_start_match = any(word.startswith(search_text) for word in name_words)

            if name_match or matricula_match or word_start_match:
                filtered.append(aluno)

        # Sort by relevance: exact matches first, then starts-with matches, then contains
        def sort_key(aluno):
            name_lower = aluno.nome.lower()
            matricula_str = str(aluno.matricula).lower()

            # Exact name match gets highest priority
            if name_lower == search_text:
                return (0, aluno.nome)
            # Exact matricula match
            elif matricula_str == search_text:
                return (1, aluno.nome)
            # Name starts with search
            elif name_lower.startswith(search_text):
                return (2, aluno.nome)
            # Any word in name starts with search
            elif any(word.startswith(search_text) for word in name_lower.split()):
                return (3, aluno.nome)
            # Name contains search
            elif search_text in name_lower:
                return (4, aluno.nome)
            # Matricula contains search
            else:
                return (5, aluno.nome)

        filtered.sort(key=sort_key)
        self._populate_table(filtered)

    def _clear_search(self):
        """Clear the search field."""
        self.search_var.set("")
        self.search_entry.focus()

    def _on_table_double_click(self, event):
        """Handle double-click on table row."""
        self._select_student()

    def _on_table_enter(self, event):
        """Handle Enter key on table."""
        self._select_student()

    def _get_selected_student(self):
        """Get the currently selected student from the table."""
        selected_rows = self.table.get_rows(selected=True)
        if not selected_rows:
            return None

        # Get matricula from the first column
        matricula = selected_rows[0].values[0]

        # Find the student object
        for aluno in self.filtered_alunos:
            if aluno.matricula == matricula:
                return aluno

        return None

    def _select_student(self):
        """Select the highlighted student and bind to card."""
        selected_aluno = self._get_selected_student()

        if not selected_aluno:
            Messagebox.show_warning(
                "Por favor, selecione um aluno da lista.", "Nenhum Aluno Selecionado"
            )
            return

        # Confirm the selection
        result = Messagebox.show_question(
            f"Vincular o cartão {self.cartao_numeracao} ao aluno:\n\n"
            f"Nome: {selected_aluno.nome}\n"
            f"Matrícula: {selected_aluno.matricula}\n\n"
            f"Confirma a vinculação?",
            "Confirmar Vinculação",
        )

        if result == "Yes":
            try:
                # Perform the binding
                if bind_matricula_to_cartao_acesso(
                    self.cartao_numeracao, selected_aluno.matricula
                ):
                    Messagebox.show_info(
                        f"Cartão {self.cartao_numeracao} vinculado com sucesso ao aluno {selected_aluno.nome}!",
                        "Vinculação Realizada",
                    )

                    # Refresh parent table and close dialog
                    if self.callback:
                        self.callback()
                    self._close_dialog()
                else:
                    Messagebox.show_error(
                        "Falha ao realizar a vinculação. Verifique os logs para mais detalhes.",
                        "Erro na Vinculação",
                    )
            except Exception as e:
                logger.error(f"Error binding card to student: {e}")
                Messagebox.show_error(
                    f"Erro ao vincular cartão: {e}", "Erro na Vinculação"
                )

    def _validate_card_number(self):
        """Validate the card number for new card creation."""
        card_number = self.card_number_var.get().strip()

        if not card_number:
            self.card_status_label.config(
                text="❌ Digite um número de cartão", foreground="red"
            )
            return False

        # Check if it's numeric
        if not card_number.isdigit():
            self.card_status_label.config(
                text="❌ O número deve conter apenas dígitos", foreground="red"
            )
            return False

        # Check length (allow up to 16 digits)
        if len(card_number) > 16:
            self.card_status_label.config(
                text="❌ Número muito longo (máximo 16 dígitos)", foreground="red"
            )
            return False

        # Format with leading zeros
        formatted_number = card_number.zfill(16)
        self.card_number_var.set(formatted_number)

        # Check if card already exists
        try:
            existing_card = CartaoAcesso.find_by_numeracao(formatted_number)
            if existing_card:
                aluno_info = (
                    f" (vinculado a {existing_card.aluno.nome})"
                    if existing_card.aluno
                    else " (não vinculado)"
                )
                self.card_status_label.config(
                    text=f"❌ Cartão {formatted_number} já existe{aluno_info}",
                    foreground="red",
                )
                return False
            else:
                self.card_status_label.config(
                    text=f"✅ Cartão {formatted_number} disponível para criação",
                    foreground="green",
                )
                return True
        except Exception as e:
            logger.error(f"Error validating card number: {e}")
            self.card_status_label.config(
                text="❌ Erro ao validar número do cartão", foreground="red"
            )
            return False

    def _create_new_card(self):
        """Create a new access card with optional student binding."""
        # Validate card number first
        if not self._validate_card_number():
            Messagebox.show_warning(
                "Por favor, digite um número de cartão válido e clique em 'Validar'.",
                "Número Inválido",
            )
            return

        card_number = self.card_number_var.get().strip()
        selected_aluno = self._get_selected_student()

        # Prepare confirmation message
        if selected_aluno:
            message = (
                f"Criar novo cartão de acesso:\n\n"
                f"Número: {card_number}\n"
                f"Vincular ao aluno: {selected_aluno.nome} ({selected_aluno.matricula})\n\n"
                f"Confirma a criação?"
            )
        else:
            message = (
                f"Criar novo cartão de acesso:\n\n"
                f"Número: {card_number}\n"
                f"⚠️ Cartão será criado SEM vinculação com aluno\n\n"
                f"Confirma a criação?"
            )

        result = Messagebox.show_question(message, "Confirmar Criação")

        if result == "Yes":
            try:
                # Create the card
                new_card = CartaoAcesso.create(numeracao=card_number)

                # Bind to student if selected
                if selected_aluno:
                    new_card.assign_to_aluno(selected_aluno.id)
                    success_message = f"Cartão {card_number} criado e vinculado com sucesso ao aluno {selected_aluno.nome}!"
                else:
                    success_message = (
                        f"Cartão {card_number} criado com sucesso! (Sem vinculação)"
                    )

                Messagebox.show_info(success_message, "Cartão Criado")
                logger.info(
                    f"New card created: {card_number}, bound to: {selected_aluno.matricula if selected_aluno else 'None'}"
                )

                # Refresh parent table and close dialog
                if self.callback:
                    self.callback()
                self._close_dialog()

            except Exception as e:
                logger.error(f"Error creating new card: {e}")
                Messagebox.show_error(f"Erro ao criar cartão: {e}", "Erro na Criação")

    def _remove_binding(self):
        """
        Remove the current binding between the card and student.

        This will set the card's aluno_id to None, effectively "unbinding" it.
        The card will then show as "Não vinculado" in the main table.
        """
        # Check if there's actually a binding to remove
        if "Não vinculado" in self.current_aluno_info:
            Messagebox.show_info(
                f"O cartão {self.cartao_numeracao} já não possui vinculação.",
                "Sem Vinculação",
            )
            return

        result = Messagebox.show_question(
            f"Remover a vinculação atual do cartão {self.cartao_numeracao}?\n\n"
            f"Vinculação atual: {self.current_aluno_info}\n\n"
            f"⚠️ O cartão ficará sem vinculação com qualquer aluno.",
            "Confirmar Remoção",
        )

        if result == "Yes":
            try:
                # Remove binding by setting to None/empty
                if bind_matricula_to_cartao_acesso(self.cartao_numeracao, None):
                    Messagebox.show_info(
                        f"Vinculação do cartão {self.cartao_numeracao} removida com sucesso!",
                        "Vinculação Removida",
                    )

                    # Refresh parent table and close dialog
                    if self.callback:
                        self.callback()
                    self._close_dialog()
                else:
                    Messagebox.show_error(
                        "Falha ao remover a vinculação. Verifique os logs para mais detalhes.",
                        "Erro na Remoção",
                    )
            except Exception as e:
                logger.error(f"Error removing card binding: {e}")
                Messagebox.show_error(
                    f"Erro ao remover vinculação: {e}", "Erro na Remoção"
                )

    def _cancel(self):
        """Cancel the dialog."""
        self._close_dialog()

    def _close_dialog(self):
        """Close the dialog."""
        self.dialog.grab_release()
        self.dialog.destroy()

    def _show_error(self, message):
        """Show error message."""
        Messagebox.show_error(message, "Erro")


class CartoesAcessoFrame(Frame):
    """
    A class that represents a frame for managing CartaoAcesso and binding them to Aluno.
    """

    def __init__(self, parent, controller, *args, **kwargs):
        """
        Initializes the CartoesAcessoFrame instance.

        :param parent: The parent widget (usually a Tk or Toplevel instance).
        :param controller: The controller for managing the application state.
        :param args: Additional positional arguments for the Frame.
        :param kwargs: Additional keyword arguments for the Frame.
        """

        super().__init__(parent, *args, **kwargs)
        self.parent = parent
        self.controller = controller

        # Button frame to hold both buttons at the top
        button_frame = ttk.Frame(self)
        button_frame.pack(expand=False, fill="x", padx=10, pady=10)

        # Import button (on the left)
        self.import_button = ttk.Button(
            button_frame,
            text="⬇ Importar",
            command=lambda: self.import_cartoes_acesso(),
            width=12,
        )
        self.import_button.pack(expand=False, padx=(0, 5), pady=0, side="left")

        # Export button (on the right of import button)
        self.export_button = ttk.Button(
            button_frame,
            text="⬆ Exportar",
            command=lambda: self.export_cartoes_acesso(),
            width=12,
        )
        self.export_button.pack(expand=False, padx=(5, 0), pady=0, side="left")

        # New card button (on the right)
        self.new_card_button = ttk.Button(
            button_frame,
            text="➕ Novo",
            command=self.open_new_card_window,
            bootstyle="success",
            width=10,
        )
        self.new_card_button.pack(expand=False, padx=(10, 0), pady=0, side="right")

        # Delete card button (on the right, next to new card)
        self.delete_card_button = ttk.Button(
            button_frame,
            text="🗑 Excluir",
            command=self.delete_selected_card,
            bootstyle="danger",
            width=10,
        )
        self.delete_card_button.pack(expand=False, padx=(10, 0), pady=0, side="right")

        # Define table columns
        cols = [
            {"text": "Cartão de Acesso", "stretch": True},
            {"text": "Aluno (Nome/Matrícula)", "stretch": True},
        ]

        # Create table container with scrollbar
        table_container = ttk.Frame(self)
        table_container.pack(expand=True, fill="both", padx=10, pady=10)

        # Create the table
        self.table = Tableview(
            table_container,
            coldata=cols,
            paginated=False,
            searchable=True,
            autofit=True,
            autoalign=False,
        )

        # Create vertical scrollbar
        v_scrollbar = ttk.Scrollbar(
            table_container, orient="vertical", command=self.table.view.yview
        )
        self.table.view.configure(yscrollcommand=v_scrollbar.set)

        # Pack table and scrollbar
        self.table.pack(side="left", expand=True, fill="both")
        v_scrollbar.pack(side="right", fill="y")

        self.table.view.bind("<Double-1>", self.handle_row_double_click)

        # Add context menu (right-click)
        self._create_context_menu()
        self.table.view.bind("<Button-3>", self.show_context_menu)  # Right-click

        # Add keyboard shortcuts
        self.table.view.bind("<Delete>", self.delete_selected_card_key)  # Delete key

        # Align headings to the center
        for cid in self.table.cidmap:
            self.table.align_heading_center(cid=cid)

        # Populate the table with data
        self.populate_table()

    def populate_table(self):
        # TODO: Show a loading indicator while fetching data

        thread = threading.Thread(target=self._populate_table)
        thread.daemon = True
        thread.start()

    def _populate_table(self):
        """
        Populates the table with CartaoAcesso and their associated Aluno.
        This runs in a background thread and schedules UI updates on the main thread.
        """
        try:
            # Fetch all CartaoAcesso records with their associated Aluno in background thread
            cartoes = CartaoAcesso.get_all()

            # Populate the table
            row_datas = []
            for i, cartao in enumerate(cartoes):
                aluno_info = (
                    f"{cartao.aluno.nome} ({cartao.aluno.matricula})"
                    if cartao.aluno
                    else "Não vinculado"
                )
                row_datas.append((cartao.numeracao, aluno_info))

            # Schedule UI update on main thread
            self.after(0, lambda: self._update_table_ui(row_datas))

        except Exception as e:
            logger.error(f"Error fetching card data: {e}")
            # Schedule error handling on main thread
            error_message = str(e)
            self.after(0, lambda: self._handle_table_error(error_message))

        # TODO: Hide loading indicator if used

    def _update_table_ui(self, rows_data):
        """
        Updates the table UI with prepared data.
        """
        # Clear existing data
        self.table.delete_rows(indices=None, iids=None)

        # Insert all rows
        for row_data in rows_data:
            self.table.insert_row("end", row_data)

        # Load the table data
        self.table.load_table_data(clear_filters=True)

    def _handle_table_error(self, error_message):
        """Handle table population errors on main thread."""
        logger.error(f"Failed to populate cards table: {error_message}")

    def handle_row_double_click(self, event, *args, **kwargs):
        """
        Handles the edit action when a user double-clicks a row.
        """
        # Get the selected row
        selected_row = self.table.get_rows(selected=True)[0].values
        cartao_numeracao = selected_row[0]
        aluno_info = selected_row[1]

        # Open a new window for editing
        self.open_edit_window(cartao_numeracao, aluno_info)

    def open_edit_window(self, cartao_numeracao, aluno_info):
        """
        Opens a new window to edit the binding of a CartaoAcesso to an Aluno.
        """
        StudentSelectionDialog(
            parent=self,
            cartao_numeracao=cartao_numeracao,
            current_aluno_info=aluno_info,
            callback=self.populate_table,
            mode="bind",
        )

    def open_new_card_window(self):
        """
        Opens a new window to create a new CartaoAcesso.
        """
        StudentSelectionDialog(parent=self, callback=self.populate_table, mode="create")

    def _create_context_menu(self):
        """Create context menu for table rows."""
        self.context_menu = ttk.Menu(self, tearoff=0)
        self.context_menu.add_command(
            label="✏️ Editar Vinculação", command=self.edit_selected_card
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="🗑️ Excluir Cartão", command=self.delete_selected_card
        )

    def show_context_menu(self, event):
        """Show context menu on right-click."""
        # Select the row under cursor
        item = self.table.view.identify_row(event.y)
        if item:
            self.table.view.selection_set(item)
            self.table.view.focus(item)

            # Show context menu
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()

    def edit_selected_card(self):
        """Edit the selected card (same as double-click)."""
        selected_rows = self.table.get_rows(selected=True)
        if not selected_rows:
            Messagebox.show_warning(
                "Por favor, selecione um cartão da lista.", "Nenhum Cartão Selecionado"
            )
            return

        # Get the selected row data
        row_data = selected_rows[0].values
        cartao_numeracao = row_data[0]
        aluno_info = row_data[1]

        # Open edit window
        self.open_edit_window(cartao_numeracao, aluno_info)

    def delete_selected_card_key(self, event):
        """Handle Delete key press."""
        self.delete_selected_card()

    def delete_selected_card(self):
        """Delete the selected card after validation."""
        selected_rows = self.table.get_rows(selected=True)
        if not selected_rows:
            Messagebox.show_warning(
                "Por favor, selecione um cartão da lista.", "Nenhum Cartão Selecionado"
            )
            return

        # Get the selected card
        row_data = selected_rows[0].values
        cartao_numeracao = row_data[0]
        aluno_info = row_data[1]

        try:
            # Find the card in database
            cartao = CartaoAcesso.find_by_numeracao(cartao_numeracao)
            if not cartao:
                Messagebox.show_error(
                    f"Cartão {cartao_numeracao} não encontrado no banco de dados.",
                    "Cartão Não Encontrado",
                )
                return

            # Check if card can be deleted
            can_delete, reason = cartao.can_be_deleted()

            if not can_delete:
                Messagebox.show_warning(
                    f"Não é possível excluir o cartão {cartao_numeracao}:\n\n{reason}\n\n"
                    "💡 Dica: Só é possível excluir cartões que não possuem registros de acesso.",
                    "Cartão Não Pode Ser Excluído",
                )
                return

            # Show confirmation dialog with details
            binding_info = (
                f"\nVinculação atual: {aluno_info}"
                if "Não vinculado" not in aluno_info
                else "\nCartão não vinculado"
            )

            result = Messagebox.show_question(
                f"⚠️ ATENÇÃO: Esta ação é irreversível!\n\n"
                f"Excluir o cartão {cartao_numeracao}?{binding_info}\n\n"
                f"✅ {reason}\n\n"
                f"Confirma a exclusão?",
                "Confirmar Exclusão",
            )

            if result == "Yes":
                # Delete the card
                success, message = cartao.delete_card()

                if success:
                    Messagebox.show_info(message, "Cartão Excluído")
                    logger.info(f"Card deleted: {cartao_numeracao}")

                    # Refresh the table
                    self.populate_table()
                else:
                    Messagebox.show_error(message, "Erro na Exclusão")
                    logger.error(f"Failed to delete card {cartao_numeracao}: {message}")

        except Exception as e:
            logger.error(f"Error deleting card {cartao_numeracao}: {e}")
            Messagebox.show_error(
                f"Erro inesperado ao excluir cartão:\n{str(e)}", "Erro na Exclusão"
            )

    def export_cartoes_acesso(self):
        """
        Exports the CartaoAcesso data to a file using cancellable operation.
        """
        # Ask user for filename and path
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            title="Salvar Cartões de Acesso",
        )

        if not filename:
            return

        # Create and run export operation
        operation = ExportCartoesOperation(filename)

        def on_result(success, error):
            if success:
                Messagebox.show_info(
                    "Cartões de Acesso exportados com sucesso!", "Sucesso"
                )
                logger.info(f"Cards exported successfully to {filename}")
            else:
                error_msg = (
                    str(error) if error else "Erro desconhecido durante exportação"
                )
                Messagebox.show_error(f"Erro ao exportar cartões: {error_msg}", "Erro")
                logger.error(f"Export failed: {error_msg}")

        # Show progress dialog
        success = show_progress_dialog(
            parent=self,
            operation=operation,
            title="Exportando Cartões de Acesso",
            allow_cancel=True,
            auto_close=True,
        )

        if success:
            on_result(True, None)
        else:
            on_result(False, None)

    def import_cartoes_acesso(self):
        """
        Imports CartaoAcesso data from a file using cancellable operation.
        """
        # Ask user for file to import
        filepath = filedialog.askopenfilename(
            title="Importar Cartões de Acesso",
            filetypes=[("Text files", "*.txt")],
        )

        if not filepath:
            return

        # Create and run import operation
        operation = ImportCartoesOperation(filepath)

        def on_result(success, error):
            if success:
                # Refresh table to show new cards
                self.populate_table()

                # Show success message with statistics
                result = operation.execute() if hasattr(operation, "_result") else {}
                imported = result.get("imported", 0)
                skipped = result.get("skipped", 0)
                errors = result.get("errors", 0)

                message = f"Importação concluída!\n\n"
                message += f"Cartões importados: {imported}\n"
                message += f"Cartões existentes (ignorados): {skipped}\n"
                if errors > 0:
                    message += f"Erros encontrados: {errors}"

                Messagebox.show_info(message, "Importação Concluída")
                logger.info(
                    f"Cards imported: {imported}, skipped: {skipped}, errors: {errors}"
                )
            else:
                # Refresh table anyway in case some cards were imported before error/cancellation
                self.populate_table()

                if error:
                    error_msg = str(error)
                    Messagebox.show_error(
                        f"Erro durante importação: {error_msg}", "Erro"
                    )
                    logger.error(f"Import failed: {error_msg}")
                else:
                    # Operation was cancelled
                    Messagebox.show_info(
                        "Importação cancelada pelo usuário.", "Cancelado"
                    )
                    logger.info("Import cancelled by user")

        # Show progress dialog
        success = show_progress_dialog(
            parent=self,
            operation=operation,
            title="Importando Cartões de Acesso",
            allow_cancel=True,
            auto_close=False,  # Don't auto-close so user can see results
        )

        # Store result for callback access
        if hasattr(operation, "imported_count"):
            operation._result = {
                "imported": operation.imported_count,
                "skipped": operation.skipped_count,
                "errors": operation.error_count,
            }

        on_result(success, None)


class AcessosFrame(Frame):
    """
    A class that represents a frame in a Tkinter application.
    Inherits from the Tkinter Frame class.
    """

    def __init__(self, parent, controller, *args, **kwargs):
        """
        Initializes the AcessosFrame instance.

        :param parent: The parent widget (usually a Tk or Toplevel instance).
        :param args: Additional positional arguments for the Frame.
        :param kwargs: Additional keyword arguments for the Frame.
        """
        super().__init__(parent, *args, **kwargs)
        self.parent = parent
        self.controller = controller

        colors = self.controller.style.colors

        # Button frame for refresh button
        button_frame = ttk.Frame(self)
        button_frame.pack(expand=False, fill="x", padx=10, pady=(10, 0))

        # Refresh button
        self.refresh_button = ttk.Button(
            button_frame,
            text="🔄 Atualizar Tabela",
            command=self.populate_table,
            bootstyle="info-outline",
        )
        self.refresh_button.pack(expand=False, side="right")

        coldata = [
            {"text": "ID", "stretch": False},  # "cid": "id",
            {"text": "Sinc.", "stretch": False},  # "cid": "synced",
            {"text": "Cartão de Acesso", "stretch": True},  # "cid": "cartao",
            # {text": "Data", "stretch": True}, # "cid": "", "
            # {text": "Hora", "stretch": True}, # "cid": "", "
            {"text": "Data e Hora", "stretch": True},  # "cid": "datetime",
            {"text": "Catraca", "stretch": True},  # "cid": "catraca",
        ]

        self.table = Tableview(
            self,
            coldata=coldata,
            paginated=True,
            pagesize=25,
            searchable=True,
            autofit=True,
            autoalign=False,
            stripecolor=(colors.light, None),
            # yscrollbar=True,
        )
        self.table.pack(expand=True, fill="both", padx=10, pady=10)
        # TODO: Where is the vertical scrollbar ?

        for cid in self.table.cidmap:
            self.table.align_heading_center(cid=cid)

        # TODO: Hide the ID column (not working...)
        self.table.get_column(0).hide()  # TODO: Use cid instead of index

        # Data insertion:
        self.populate_table()

    def populate_table(self):
        """
        Populates the table with data from the database.
        """
        # TODO: Use a loading indicator while fetching data

        # Run in a separate thread to avoid blocking UI
        thread = threading.Thread(target=self._populate_table_thread)
        thread.daemon = True
        thread.start()

    def _populate_table_thread(self):
        """
        Thread worker for populating the table.
        """
        # Fetch data in background thread
        acessos = Acesso.get_all()

        # Prepare all data
        rows_data = []
        for acesso in acessos:
            synced = "✅" if acesso.synced else "🚫"
            cartao = acesso.cartao_acesso.numeracao
            data_hora = datetime.combine(acesso.date, acesso.time)
            catraca = acesso.catraca

            rows_data.append(
                (
                    acesso.id,
                    synced,
                    cartao,
                    data_hora,
                    catraca,
                )
            )

        # Update UI in main thread
        self.after(0, lambda: self._update_table_ui(rows_data))

        # TODO: Hide loading indicator if used

    def _update_table_ui(self, rows_data):
        """
        Updates the table UI with prepared data.
        """
        # Clear existing data
        self.table.delete_rows(indices=None, iids=None)

        # Insert all rows
        for row_data in rows_data:
            self.table.insert_row("end", row_data)

        # Load the table data
        self.table.load_table_data(clear_filters=True)

    def update_sync_status(self, acesso_ids):
        """
        Updates the sync status of specific rows in the table.
        This method handles both visible and non-visible rows (due to pagination).

        :param acesso_ids: List of access IDs that have been synced.
        """
        if not acesso_ids:
            return

        logger.debug(f"Updating sync status for {len(acesso_ids)} access records")

        updated_count = 0

        # Update visible rows first (for immediate visual feedback)
        for row in self.table.tablerows:
            if row.values[0] in acesso_ids:
                row.values[1] = "✅"
                row.refresh()
                updated_count += 1

        # If some IDs weren't found in visible rows (due to pagination/filtering),
        # schedule a table refresh to ensure all updates are reflected
        if updated_count < len(acesso_ids):
            logger.debug(
                f"Updated {updated_count}/{len(acesso_ids)} visible rows, scheduling table refresh"
            )
            # Use after to avoid blocking the UI
            self.after(100, self.refresh_table_data)
        else:
            logger.debug(f"Successfully updated {updated_count} visible rows")

    def refresh_table_data(self):
        """
        Refreshes the table data without losing current page/filter state.
        This is more efficient than a full repopulate for sync status updates.
        """
        logger.debug("Refreshing table data to reflect sync status changes")

        # Store current state
        current_page = getattr(self.table, "page", 0)
        current_search = getattr(self.table, "searchterm", "")

        # Refresh the data
        thread = threading.Thread(
            target=self._refresh_table_thread, args=(current_page, current_search)
        )
        thread.daemon = True
        thread.start()

    def _refresh_table_thread(self, current_page, current_search):
        """
        Background thread to refresh table data while preserving state.
        """
        try:
            # Fetch fresh data
            acessos = Acesso.get_all()

            # Prepare updated data
            rows_data = []
            for acesso in acessos:
                synced = "✅" if acesso.synced else "🚫"
                cartao = acesso.cartao_acesso.numeracao
                data_hora = datetime.combine(acesso.date, acesso.time)
                catraca = acesso.catraca

                rows_data.append(
                    (
                        acesso.id,
                        synced,
                        cartao,
                        data_hora,
                        catraca,
                    )
                )

            # Update UI in main thread while preserving state
            self.after(
                0,
                lambda: self._update_table_preserving_state(
                    rows_data, current_page, current_search
                ),
            )

        except Exception as e:
            logger.error(f"Error refreshing table data: {e}")

    def _update_table_preserving_state(self, rows_data, current_page, current_search):
        """
        Updates table data while preserving pagination and search state.
        """
        try:
            # Clear and reload data
            self.table.delete_rows(indices=None, iids=None)

            for row_data in rows_data:
                self.table.insert_row("end", row_data)

            # Reload table data
            self.table.load_table_data(clear_filters=False)

            # Restore search if there was one
            if current_search:
                # Restore search term (the table should remember this)
                pass

            # Restore page if possible (the table handles this automatically)
            logger.debug("Table data refreshed successfully")

        except Exception as e:
            logger.error(f"Error updating table state: {e}")
            # Fallback to simple update
            self._update_table_ui(rows_data)

    def handle_new_data_processed(self, new_record_count=0):
        """
        Called when new data has been processed into the database.
        Refreshes the entire table to show new records.

        :param new_record_count: Number of new records added (for logging)
        """
        if new_record_count > 0:
            logger.info(
                f"New data processed: {new_record_count} records. Refreshing table..."
            )
            # For new data, we need a full refresh
            self.populate_table()
        else:
            logger.debug("No new records to display")


class ConfigurationFrame(Frame):
    """
    A class that represents a frame in a Tkinter application.
    Inherits from the Tkinter Frame class.
    """

    def __init__(self, parent, controller, *args, **kwargs):
        """
        Initializes the ActivitySoftFrame instance.

        :param parent: The parent widget (usually a Tk or Toplevel instance).
        :param args: Additional positional arguments for the Frame.
        :param kwargs: Additional keyword arguments for the Frame.
        """

        super().__init__(parent, *args, **kwargs)
        self.parent = parent
        self.controller = controller

        # Bilhetes Path
        self.lf_bilhetes = ttk.LabelFrame(self, text="Bilhetes")
        self.lf_bilhetes.pack(expand=False, fill="x", padx=10, pady=10)

        self.bilhetes_path = ttk.StringVar()
        if bilhete_path := get_bilhetes_path():
            self.bilhetes_path.set(bilhete_path)

        self.entry_bilhetes_path = ttk.Entry(
            self.lf_bilhetes,
            textvariable=self.bilhetes_path,
        )
        self.entry_bilhetes_path.pack(
            expand=True, fill="x", padx=10, pady=10, side="left"
        )

        self.btn_bilhetes_path = ttk.Button(
            self.lf_bilhetes,
            text="Procurar",
            command=self.browse_bilhetes_path,
        )
        self.btn_bilhetes_path.pack(expand=False, padx=10, pady=10, side="left")

        # Data e Hora:
        self.lf_datas = ttk.LabelFrame(self, text="Configurações de Data e Hora")
        self.lf_datas.pack(expand=False, fill="x", padx=10, pady=10)

        # Cutoff:
        self.cutoff = ttk.StringVar()
        self.cutoff.set(get_cutoff())

        self.lf_cutoff = ttk.LabelFrame(self.lf_datas, text="Filtro de Data (Cutoff)")
        self.lf_cutoff.pack(expand=True, fill="x", side="left", padx=10, pady=10)

        self.de_cutoff = ttk.DateEntry(self.lf_cutoff, dateformat="%d/%m/%Y")
        self.de_cutoff.pack(expand=True, fill="both", padx=10, pady=10)
        self.de_cutoff.entry.config(textvariable=self.cutoff)

        # Intervalo:
        self.intervalo = ttk.IntVar()
        self.intervalo.set(get_interval())

        self.lf_intervalo = ttk.LabelFrame(
            self.lf_datas, text=f"Intervalo [{MIN_INTERVAL}-{MAX_INTERVAL}] minutos"
        )
        self.lf_intervalo.pack(expand=True, fill="both", side="left", padx=10, pady=10)

        self.spin_intervalo = ttk.Spinbox(
            self.lf_intervalo,
            from_=MIN_INTERVAL,
            to=MAX_INTERVAL,
            textvariable=self.intervalo,
            increment=1,
            validate="all",
            validatecommand=(self.register(self.validate_interval), "%P"),
        )
        self.spin_intervalo.pack(expand=True, fill="both", padx=10, pady=10)

        # ActivitySoft API Key
        self.api_key = ttk.StringVar()
        if api_key := get_api_key():
            self.api_key.set(api_key)
        else:
            self.api_key.set("")

        self.lf_api = ttk.LabelFrame(self, text="ActivitySoft API Key")
        self.lf_api.pack(expand=False, fill="x", padx=10, pady=10)

        self.entry_api = ttk.Entry(
            self.lf_api,
            textvariable=self.api_key,
            show="*",
            state="readonly",
        )
        self.entry_api.pack(
            expand=True,
            fill="x",
            padx=10,
            pady=10,
            side="left",
        )

        self.change_api = ttk.StringVar()
        self.change_api.set("")

        self.cb_edit_api = ttk.Checkbutton(
            self.lf_api,
            text="Editar",
            variable=self.change_api,
            onvalue="1",
            offvalue="0",
            command=lambda: self.enable_entry_api(),
        )
        self.cb_edit_api.pack(expand=False, padx=10, pady=10, side="left")

        # Save Button
        self.btn_save = ttk.Button(
            self,
            text="Salvar Configurações",
            command=self.save_config,
        )
        self.btn_save.pack(expand=False, padx=10, pady=10)

    def validate_interval(self, value):
        """
        Validates the interval value to ensure it stays within the allowed range.
        """

        try:
            value = int(value)
            if value < MIN_INTERVAL:
                self.intervalo.set(MIN_INTERVAL)  # Force minimum value
                return False
            elif value > MAX_INTERVAL:
                self.intervalo.set(MAX_INTERVAL)  # Force maximum value
                return False
            return True
        except ValueError:
            self.intervalo.set(DEFAULT_INTERVAL)  # Default to minimum if invalid input
            return False

    def browse_bilhetes_path(self):
        """
        Opens a file dialog to select a path for the bilhetes.
        """
        filepath = filedialog.askopenfilename(
            filetypes=(
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            )
        )

        if filepath:
            self.bilhetes_path.set(filepath)

    def enable_entry_api(self):
        """
        Enables the entry field for the ActivitySoft API key.
        """

        if self.change_api.get() == "1":
            self.entry_api.config(state="normal")
            self.api_key.set("")
        else:
            self.entry_api.config(state="readonly")
            self.api_key.set(get_api_key())

    def save_config(self):
        """
        Saves the configuration settings.
        """
        bilhete_path = self.bilhetes_path.get()
        activitysoft_key = self.entry_api.get()
        intervalo = self.intervalo.get()
        cutoff = self.cutoff.get()

        # Save the settings to the database
        set_bilhetes_path(bilhete_path)
        set_interval(intervalo)
        set_api_key(activitysoft_key)
        set_cutoff(cutoff)

        # Update the settings in the controller
        self.controller.start_processing_threads()

        # Show a success message
        Messagebox().show_info(
            title="Configurações Salvas",
            message="As configurações foram salvas com sucesso!",
        )


class TaskMonitorFrame(Frame):
    """
    A frame for monitoring the status of background tasks with progress bars and status indicators.
    Polls task status from the task registry instead of using queues.
    """

    def __init__(self, parent, controller, *args, **kwargs):
        """
        Initializes the TaskMonitorFrame instance.
        """
        super().__init__(parent, *args, **kwargs)
        self.parent = parent
        self.controller = controller

        # Main container
        main_frame = ttk.Frame(self)
        main_frame.pack(expand=True, fill="both", padx=20, pady=20)

        # Title
        title_label = ttk.Label(
            main_frame, text="Monitor de Tarefas", font=("Arial", 16, "bold")
        )
        title_label.pack(pady=(0, 20))

        # Task monitoring containers
        self.task_frames = {}
        self.progress_bars = {}
        self.status_labels = {}
        self.time_labels = {}
        self.detail_labels = {}

        # Create monitoring widgets for each task
        tasks = [
            (
                "file_reader",
                "📄 Leitor de Arquivo",
                "Lê novos dados do arquivo bilhetes.txt",
            ),
            (
                "db_processor",
                "🗄️ Processador de Banco",
                "Processa eventos na base de dados",
            ),
            (
                "db_sync",
                "🔄 Sincronização API",
                "Sincroniza registros com ActivitySoft",
            ),
        ]

        for task_id, task_name, task_description in tasks:
            self._create_task_monitor(main_frame, task_id, task_name, task_description)

        # Start polling for task updates
        self._start_status_polling()

    def _create_task_monitor(self, parent, task_id, task_name, task_description):
        """Create monitoring widgets for a single task."""

        # Task container
        task_frame = ttk.LabelFrame(parent, text=task_name, padding=15)
        task_frame.pack(fill="x", pady=10)
        self.task_frames[task_id] = task_frame

        # Description
        desc_label = ttk.Label(
            task_frame, text=task_description, font=("Arial", 9), foreground="gray"
        )
        desc_label.pack(anchor="w", pady=(0, 10))

        # Status and time row
        status_time_frame = ttk.Frame(task_frame)
        status_time_frame.pack(fill="x", pady=(0, 10))

        # Status label
        status_label = ttk.Label(
            status_time_frame, text="⏳ Iniciando...", font=("Arial", 10, "bold")
        )
        status_label.pack(side="left")
        self.status_labels[task_id] = status_label

        # Time label
        time_label = ttk.Label(
            status_time_frame,
            text="Última execução: --:--:--",
            font=("Arial", 9),
            foreground="gray",
        )
        time_label.pack(side="right")
        self.time_labels[task_id] = time_label

        # Progress bar
        progress_bar = ttk.Progressbar(
            task_frame, mode="indeterminate", bootstyle="info", length=400
        )
        progress_bar.pack(fill="x", pady=(0, 10))
        self.progress_bars[task_id] = progress_bar

        # Detail label
        detail_label = ttk.Label(
            task_frame,
            text="Aguardando início da tarefa...",
            font=("Arial", 8),
            foreground="gray",
        )
        detail_label.pack(anchor="w")
        self.detail_labels[task_id] = detail_label

    def _start_status_polling(self):
        """Start polling task status from the controller's task instances."""
        self._update_all_tasks()
        # Schedule next update
        self.after(100, self._start_status_polling)

    def _update_all_tasks(self):
        """Update all task displays by reading from the controller's task instances."""
        # Get task instances directly from controller
        tasks = {
            "file_reader": getattr(self.controller, "file_reader_task", None),
            "db_processor": getattr(self.controller, "db_processor_task", None),
            "db_sync": getattr(self.controller, "db_sync_task", None),
        }

        for task_id, task in tasks.items():
            if task and task_id in self.task_frames:
                self._update_task_display(task_id, task)
            elif task_id in self.task_frames:
                # Task not yet initialized, show waiting state
                self._update_task_display_waiting(task_id)

    def _update_task_display(self, task_id, task):
        """Update the display for a specific task."""
        if task_id not in self.progress_bars:
            return

        progress_bar = self.progress_bars[task_id]
        status_label = self.status_labels[task_id]
        time_label = self.time_labels[task_id]
        detail_label = self.detail_labels[task_id]

        state = task.state
        details = task.details
        last_run_time = task.last_run_time
        error_message = task.error_message

        # Update based on state
        if state == TaskState.STARTING:
            status_label.config(text="🚀 Iniciando", foreground="purple")
            progress_bar.config(mode="indeterminate", bootstyle="info")
            progress_bar.start()

        elif state == TaskState.RUNNING:
            status_label.config(text="🟢 Executando", foreground="green")
            progress_bar.config(mode="indeterminate", bootstyle="success")
            progress_bar.start()

        elif state == TaskState.WAITING:
            status_label.config(text="⏳ Aguardando", foreground="blue")
            progress_bar.config(mode="determinate", bootstyle="info")
            progress_bar.config(value=0)
            progress_bar.stop()

        elif state == TaskState.SUCCESS:
            status_label.config(text="✅ Concluído", foreground="green")
            progress_bar.config(mode="determinate", bootstyle="success")
            progress_bar.config(value=100)
            progress_bar.stop()

        elif state == TaskState.ERROR:
            status_label.config(text="❌ Erro", foreground="red")
            progress_bar.config(mode="determinate", bootstyle="danger")
            progress_bar.config(value=0)
            progress_bar.stop()

        elif state == TaskState.WARNING:
            status_label.config(text="⚠️ Aviso", foreground="orange")
            progress_bar.config(mode="determinate", bootstyle="warning")
            progress_bar.config(value=100)
            progress_bar.stop()

        elif state == TaskState.CANCELLED:
            status_label.config(text="🚫 Cancelado", foreground="gray")
            progress_bar.config(mode="determinate", bootstyle="secondary")
            progress_bar.config(value=0)
            progress_bar.stop()

        else:  # STOPPED or unknown
            status_label.config(text="⏹️ Parado", foreground="gray")
            progress_bar.config(mode="determinate", bootstyle="secondary")
            progress_bar.config(value=0)
            progress_bar.stop()

        # Update time and details
        if last_run_time:
            try:
                time_label.config(
                    text=f"Última execução: {last_run_time.strftime('%H:%M:%S')}"
                )
            except (AttributeError, ValueError) as e:
                logger.warning(f"Error formatting last_run_time for {task_id}: {e}")
                time_label.config(text="Última execução: --:--:--")

        if details:
            detail_label.config(text=details)
        elif error_message:
            detail_label.config(text=f"Erro: {error_message}")
        else:
            detail_label.config(text="Aguardando...")

    def _update_task_display_waiting(self, task_id):
        """Update display for a task that hasn't been registered yet."""
        if task_id not in self.progress_bars:
            return

        progress_bar = self.progress_bars[task_id]
        status_label = self.status_labels[task_id]
        detail_label = self.detail_labels[task_id]

        status_label.config(text="⏳ Aguardando", foreground="blue")
        progress_bar.config(mode="determinate", bootstyle="info")
        progress_bar.config(value=0)
        progress_bar.stop()
        detail_label.config(text="Aguardando registro da tarefa...")

    def set_task_status(self, task_id, state, details="", last_run_time=None):
        """
        Legacy method for compatibility.
        Tasks should now update their status directly through the task registry.
        """
        # This method is kept for backward compatibility but should not be used
        # with the new task monitoring system
        logger.warning(
            f"Legacy set_task_status called for {task_id}. "
            "Tasks should update their status through the task registry."
        )

    def _update_single_task(self, task_id, status):
        """Legacy method kept for compatibility."""
        # This method is no longer used with the new polling system
        pass
