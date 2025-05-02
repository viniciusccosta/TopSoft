import logging
import threading

import ttkbootstrap as ttk
from decouple import config
from PIL import Image
from pystray import Icon, Menu, MenuItem
from rich.logging import RichHandler

from topsoft.db import init_db
from topsoft.frames import AcessosFrame, CartoesAcessoFrame, ConfigurationFrame
from topsoft.tasks import task_processamento, task_update_checker
from topsoft.utils import get_path

logger = logging.getLogger(__name__)


class App(ttk.Window):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Window:
        self.title("TopSoft")
        self.geometry("800x600")

        # Window Icon:
        self.iconbitmap(get_path("topsoft.ico"))

        # Windows Closing:
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Notebook
        self.notebook = ttk.Notebook(self)

        # Frames:
        self.frames = {
            # "TopSoft": MainFrame(self.notebook, controller=self),
            "Cartões de Acesso": CartoesAcessoFrame(self.notebook, controller=self),
            "Acessos": AcessosFrame(self.notebook, controller=self),
            "Configurações": ConfigurationFrame(self.notebook, controller=self),
        }

        for name, frame in self.frames.items():
            self.notebook.add(frame, text=name)

        # Notebook:
        self.notebook.pack(expand=True, fill="both")

        # Processamento:
        self.processing_thread = None
        self.processing_stop_event = threading.Event()
        self.start_processing_thread()

        # System Tray:
        self.tray_icon = None
        self.create_tray_icon()

        # Check for updates:
        self.update_stop_event = threading.Event()
        self.update_thread = threading.Thread(
            target=task_update_checker,
            args=(self.update_stop_event,),
            daemon=True,
        )
        self.update_thread.start()

    def create_tray_icon(self):
        """
        Create a system tray icon for the application.
        """

        image = Image.open(get_path("topsoft.ico"))

        menu = Menu(
            MenuItem("Show", self.show_window),
            MenuItem("Exit", self.exit_app),
        )

        self.tray_icon = Icon("TopSoft", image, "TopSoft", menu)

        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def start_processing_thread(self):
        """
        Start the background task in a separate thread.
        """

        # Stop the previous thread if it's running
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_stop_event.set()
            self.processing_thread.join()

        # Start a new thread
        self.processing_stop_event.clear()
        self.processing_thread = threading.Thread(
            target=task_processamento,
            args=(self.processing_stop_event,),
            daemon=True,
        )
        self.processing_thread.start()

    def on_closing(self):
        """
        Handle the window closing event.
        """

        self.withdraw()

    def show_window(self):
        """
        Handle the window open event.
        """

        self.deiconify()

    def exit_app(self):
        """
        Handle the exit event.
        """
        logger.debug("Exiting application.")

        # Stop the processing thread
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_stop_event.set()
            self.processing_thread.join()

        # Stop the Tray Icon thread
        if self.tray_icon:
            self.tray_icon.stop()

        # Stop the update thread
        if self.update_thread and self.update_thread.is_alive():
            self.update_stop_event.set()
            self.update_thread.join()

        # Destroy the window
        self.destroy()

    def run(self):
        init_db()  # TODO: Não tenho certeza se é o local mais adequado para isso
        self.mainloop()


def configure_logger():
    """
    Configure the logger for the application.
    """

    log_level = config("LOGGING_LEVEL", default=logging.INFO)

    # Handlers:
    file_handler = logging.FileHandler("topsoft.log")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s"
        )
    )

    console_handler = RichHandler(rich_tracebacks=True)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(funcName)s - %(message)s")
    )

    # Logger:
    logging.basicConfig(
        level=log_level,
        handlers=[console_handler, file_handler],
    )


if __name__ == "__main__":
    configure_logger()

    app = App()
    app.run()
