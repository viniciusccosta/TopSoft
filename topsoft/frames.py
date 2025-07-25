import logging
import threading
from datetime import datetime
from time import sleep
from tkinter import Frame, filedialog

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.tableview import Tableview

from topsoft.constants import DEFAULT_INTERVAL, MAX_INTERVAL, MIN_INTERVAL
from topsoft.models import Acesso, Aluno, CartaoAcesso
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
        """
        # Clear existing data
        self.table.delete_rows(indices=None, iids=None)
        # TODO: Just update without clearing the table

        # Fetch all CartaoAcesso records with their associated Aluno
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

        self.after(0, lambda: self._update_table_ui(row_datas))

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
        Exports the CartaoAcesso data to a file.
        This function is called when the user clicks the export button.
        """

        # 1) Retrieve all CartaoAcesso directly from the database
        cartoes = CartaoAcesso.get_all()

        # 2) Format the data according to the expected output
        formatted_data = []
        for cartao in cartoes:
            # Ensure the card number is 16 characters long, padded with zeros
            card_number = str(cartao.numeracao).zfill(16)

            # Ensure the name is left-aligned and up to 40 characters long
            name = f"{cartao.aluno.nome if cartao.aluno else 'Não vinculado':<40}"

            # Append the formatted string
            formatted_data.append(f"{card_number}{name}00110")

        # 3) Ask user for filename and path
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            title="Salvar Cartões de Acesso",
        )

        # 4) Write the formatted data to a file
        if filename:
            with open(filename, "w", encoding="utf-8") as file:
                for line in formatted_data:
                    file.write(line + "\n")

    def import_cartoes_acesso(self):
        """
        Imports CartaoAcesso data from a file.
        This function is called when the user clicks the import button.
        """

        # Ask user for file to import
        filepath = filedialog.askopenfilename(
            title="Importar Cartões de Acesso",
            filetypes=[("Text files", "*.txt")],
        )

        if not filepath:
            return

        # Read the file and gather data
        with open(filepath, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if line and len(line) >= 56:  # Ensure line is long enough
                    numero = line[0:16]
                    nome = line[16 : 16 + 40].strip()

                    # Create a new CartaoAcesso instance
                    cartao, created = CartaoAcesso.get_or_create(numeracao=numero)

                    # If the card already exists, skip to the next line
                    if not created:
                        logger.info(f"Cartão de Acesso {numero} já existe, pulando...")
                        continue

                    # TODO: Uma possibilidade seria vincular um cartão, que ainda não foi vinculado, a um aluno existente
                    # TODO: Outra possibilidade seria atualizar o cartão a cada importação

                    # Set the associated Aluno if the name is provided
                    # TODO: Lidar com caso de nomes duplicados
                    aluno = Aluno.find_by_name(nome)

                    if aluno:
                        cartao.aluno = aluno
                        cartao.save()
                        logger.info(
                            f"Cartão de Acesso {numero} criado e vinculado a Aluno {nome}"
                        )
                    else:
                        logger.info(f"Cartão de Acesso {numero} criado")

        # TODO: Bulk get/create/update CartaoAcesso and Aluno instead within a loop


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
        Updates the sync status of a specific row in the table.

        :param row_id: The ID of the row to update.
        :param synced: The new sync status (True or False).
        """

        # TODO: Use a dict instead of iterating through rows to find the right row

        logger.debug(f"Updating sync status for access {len(acesso_ids)} IDs")

        for row in self.table.tablerows:
            if row.values[0] in acesso_ids:
                # TODO: Not sure if this is the best way to update the row...
                row.values[1] = "✅"
                row.refresh()


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
        self.controller.start_processing_thread()

        # Show a success message
        Messagebox().show_info(
            title="Configurações Salvas",
            message="As configurações foram salvas com sucesso!",
        )
