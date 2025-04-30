from datetime import datetime
from tkinter import Frame, filedialog

import ttkbootstrap as ttk
from ttkbootstrap.tableview import Tableview

from topsoft.constants import DEFAULT_INTERVAL, MAX_INTERVAL, MIN_INTERVAL
from topsoft.repository import get_acessos
from topsoft.secrets import get_api_key, set_api_key
from topsoft.settings import (
    get_bilhetes_path,
    get_cutoff,
    get_interval,
    set_bilhetes_path,
    set_cutoff,
    set_interval,
)


class CartoesAcessoFrame(Frame):
    """
    A class that represents a frame in a Tkinter application.
    Inherits from the Tkinter Frame class.
    """

    def __init__(self, parent, controller, *args, **kwargs):
        """
        Initializes the CartoesAcessoFrame instance.

        :param parent: The parent widget (usually a Tk or Toplevel instance).
        :param args: Additional positional arguments for the Frame.
        :param kwargs: Additional keyword arguments for the Frame.
        """
        super().__init__(parent, *args, **kwargs)
        self.parent = parent
        self.controller = controller


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

        cols = [
            # {"text": "ID", "stretch": False},
            {"text": "Sinc.", "stretch": False},
            {"text": "Cartão de Acesso", "stretch": True},
            # {"text": "Data", "stretch": True},
            # {"text": "Hora", "stretch": True},
            {"text": "Data e Hora", "stretch": True},
            {"text": "Catraca", "stretch": True},
        ]

        self.table = Tableview(
            self,
            coldata=cols,
            paginated=False,
            searchable=True,
            autofit=True,
            autoalign=False,
        )
        self.table.pack(expand=True, fill="both", padx=10, pady=10)

        for cid in self.table.cidmap:
            self.table.align_heading_center(cid=cid)

        # Schedule data insertion after initialization
        self.after(100, self.populate_table)

    def populate_table(self):
        """
        Populates the table with data from the database.
        """

        # Clear existing data
        self.table.delete_rows(indices=None, iids=None)

        # Get the current page index and page size
        current_page = int(self.table._pageindex.get())
        page_size = int(self.table.pagesize)

        # Calculate the offset for pagination
        offset = current_page * page_size

        # Fetch data for the current page
        for acesso in get_acessos(limit=1000):
            synced = "✅" if acesso.synced else "🚫"
            cartao = acesso.cartao_acesso.numeracao
            # data = acesso.date.strftime("%d/%m/%Y")
            # hora = acesso.time.strftime("%H:%M")
            data_hora = datetime.combine(acesso.date, acesso.time)
            catraca = acesso.catraca

            self.table.insert_row("end", (synced, cartao, data_hora, catraca))

        # Load the table data
        self.table.load_table_data(clear_filters=True)


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

        # TODO: Kill the background task and restart it with the new settings
        self.controller.start_thread()
