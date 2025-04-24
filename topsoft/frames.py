from tkinter import Frame, filedialog

import ttkbootstrap as ttk

from topsoft.database import (
    get_api_key,
    get_bilhetes_path,
    get_interval,
    set_api_key,
    set_bilhetes_path,
    set_interval,
)


class MainFrame(Frame):
    """
    A class that represents a frame in a Tkinter application.
    Inherits from the Tkinter Frame class.
    """

    def __init__(self, parent, controller, *args, **kwargs):
        """
        Initializes the TopSoftFrame instance.

        :param parent: The parent widget (usually a Tk or Toplevel instance).
        :param args: Additional positional arguments for the Frame.
        :param kwargs: Additional keyword arguments for the Frame.
        """
        super().__init__(parent, *args, **kwargs)
        self.parent = parent
        self.controller = controller


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

        self.bilhete_path = ttk.StringVar()
        self.bilhete_path.set(get_bilhetes_path())

        self.entry_bilhetes_path = ttk.Entry(
            self.lf_bilhetes,
            textvariable=self.bilhete_path,
        )
        self.entry_bilhetes_path.pack(
            expand=True, fill="x", padx=10, pady=10, side="left"
        )

        self.btn_bilhetes_path = ttk.Button(
            self.lf_bilhetes,
            text="Browse",
            command=self.browse_bilhetes_path,
        )
        self.btn_bilhetes_path.pack(expand=False, padx=10, pady=10, side="left")

        # ActivitySoft API Key
        try:
            api_key = get_api_key()
        except RuntimeError:
            api_key = None

        self.as_key = ttk.StringVar()
        self.as_key.set("****************" if api_key else "NOT SET")

        self.lf_activitysoft = ttk.LabelFrame(self, text="ActivitySoft API Key")
        self.lf_activitysoft.pack(expand=False, fill="x", padx=10, pady=10)

        self.entry_activitysoft_key = ttk.Entry(
            self.lf_activitysoft,
            textvariable=self.as_key,
            show="*",
        )
        self.entry_activitysoft_key.pack(expand=True, fill="x", padx=10, pady=10)

        # Interval
        self.intervalo = ttk.IntVar()
        self.intervalo.set(get_interval())

        self.lf_interval = ttk.LabelFrame(
            self, text="Intervalo (em segundos) [60-86400]"
        )
        self.lf_interval.pack(expand=False, fill="x", padx=10, pady=10)

        self.spin_intervalo = ttk.Spinbox(
            self.lf_interval,
            from_=60,
            to=86400,
            textvariable=self.intervalo,
            increment=1,
            validate="all",
            validatecommand=(self.register(self.validate_interval), "%P"),
        )
        self.spin_intervalo.pack(expand=True, fill="x", padx=10, pady=10)

        # Save Button
        self.btn_save = ttk.Button(
            self,
            text="Salvar",
            command=self.save_config,
        )
        self.btn_save.pack(expand=False, padx=10, pady=10)

    def validate_interval(self, value):
        """
        Validates the interval value to ensure it stays within the allowed range.
        """
        try:
            value = int(value)
            if value < 60:
                self.intervalo.set(60)  # Force minimum value
                return False
            elif value > 86400:
                self.intervalo.set(86400)  # Force maximum value
                return False
            return True
        except ValueError:
            self.intervalo.set(60)  # Default to minimum if invalid input
            return False

    def browse_bilhetes_path(self):
        """
        Opens a file dialog to select a path for the bilhetes.
        """
        path = filedialog.askopenfilename()
        if path:
            self.bilhete_path.set(path)
            self.entry_bilhetes_path.delete(0, "end")
            self.entry_bilhetes_path.insert(0, path)

        self.entry_bilhetes_path.update()

    def save_config(self):
        """
        Saves the configuration settings.
        """
        bilhete_path = self.bilhete_path.get()
        activitysoft_key = self.entry_activitysoft_key.get()
        intervalo = self.intervalo.get()

        # Save the settings to the database
        set_bilhetes_path(bilhete_path)
        set_interval(intervalo)
        set_api_key(activitysoft_key)

        # TODO: Kill the background task and restart it with the new settings
        self.controller.start_thread()
