import logging
import threading

import ttkbootstrap as ttk
from decouple import config
from PIL import Image
from pystray import Icon, Menu, MenuItem
from rich.logging import RichHandler

from topsoft.db import init_db
from topsoft.frames import AcessosFrame, CartoesAcessoFrame, ConfigurationFrame
from topsoft.tasks import background_task
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

        # Thread:
        self.thread = None
        self.stop_event = threading.Event()
        self.start_thread()

        # Windows Closing:
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # System Tray:
        self.tray_icon = None
        self.create_tray_icon()

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

    def start_thread(self):
        """
        Start the background task in a separate thread.
        """
        # Stop the previous thread if it's running
        if self.thread and self.thread.is_alive():
            logging.warning("Thread is already running.")
            self.stop_thread()

        # Start a new thread
        self.stop_event.clear()
        self.thread = threading.Thread(
            target=background_task,
            args=(self.stop_event,),
            daemon=True,
        )
        self.thread.start()

    def stop_thread(self):
        """
        Stop the background task thread.
        """
        if self.thread and self.thread.is_alive():
            logging.info("Stopping thread.")
            self.stop_event.set()
            self.thread.join()
        else:
            logging.warning("Thread is not running.")

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

        self.stop_thread()
        if self.tray_icon:
            self.tray_icon.stop()
        self.destroy()

    def run(self):
        init_db()
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
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    console_handler = RichHandler(rich_tracebacks=True)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(message)s")
    )

    # Logger:
    logging.basicConfig(
        level=log_level,
        handlers=[console_handler, file_handler],
    )


if __name__ == "__main__":
    # TODO: Auto check for updates

    configure_logger()

    app = App()
    app.run()
