import logging
import threading
from datetime import datetime
from time import sleep
from tkinter import Frame, filedialog

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
            text="Importar Cartões",
            command=lambda: self.import_cartoes_acesso(),
        )
        self.import_button.pack(expand=False, padx=(0, 5), pady=0, side="left")

        # Export button (on the right of import button)
        self.export_button = ttk.Button(
            button_frame,
            text="Exportar Cartões",
            command=lambda: self.export_cartoes_acesso(),
        )
        self.export_button.pack(expand=False, padx=(5, 0), pady=0, side="left")

        # Define table columns
        cols = [
            {"text": "Cartão de Acesso", "stretch": True},
            {"text": "Aluno (Nome/Matrícula)", "stretch": True},
        ]

        # Create the table
        self.table = Tableview(
            self,
            coldata=cols,
            paginated=False,
            searchable=True,
            autofit=True,
            autoalign=False,
            # yscrollbar=True,
        )
        self.table.pack(expand=True, fill="both", padx=10, pady=10)
        # TODO: Where is the vertical scrollbar ?

        self.table.view.bind("<Double-1>", self.handle_row_double_click)

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
        edit_window = ttk.Toplevel(self)
        edit_window.title("Editar Vinculação de Cartão")
        edit_window.geometry("400x200")

        # Display the current CartaoAcesso
        ttk.Label(edit_window, text=f"Cartão de Acesso: {cartao_numeracao}").pack(
            padx=10, pady=10
        )

        # Dropdown for selecting a new Aluno # TODO: Add a search filter
        ttk.Label(edit_window, text="Vincular a Aluno:").pack(padx=10, pady=5)
        aluno_var = ttk.StringVar()
        aluno_dropdown = ttk.Combobox(edit_window, textvariable=aluno_var)
        aluno_dropdown.pack(padx=10, pady=5)

        # Fetch all Aluno records for the dropdown
        alunos = Aluno.get_all(sort_by="nome")
        aluno_dropdown["values"] = [
            f"{aluno.nome} ({aluno.matricula})" for aluno in alunos
        ]

        # Save button
        def save_binding():
            selected_aluno = aluno_dropdown.get()
            if selected_aluno:
                aluno_matricula = selected_aluno.split("(")[-1].strip(")")

                if bind_matricula_to_cartao_acesso(cartao_numeracao, aluno_matricula):
                    self.populate_table()
                    edit_window.destroy()

        ttk.Button(edit_window, text="Salvar", command=save_binding).pack(
            padx=10, pady=10
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
