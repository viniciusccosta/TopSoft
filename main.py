import logging
import threading
from queue import Empty, Queue

import ttkbootstrap as ttk
from PIL import Image
from pystray import Icon, Menu, MenuItem

from topsoft.config import configure_logger
from topsoft.database import configure_database
from topsoft.frames import AcessosFrame, CartoesAcessoFrame, ConfigurationFrame
from topsoft.tasks import task_processamento
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
            "Cartões de Acesso": CartoesAcessoFrame(self.notebook, controller=self),
            "Acessos": AcessosFrame(self.notebook, controller=self),
            "Configurações": ConfigurationFrame(self.notebook, controller=self),
        }

        for name, frame in self.frames.items():
            self.notebook.add(frame, text=name)

        # Notebook:
        self.notebook.pack(expand=True, fill="both")

        # Processamento:
        self.processing_queue = None
        self.processing_thread = None
        self.processing_stop_event = threading.Event()
        self.start_processing_thread()

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

    def start_processing_thread(self):
        """
        Start the background task in a separate thread.
        """

        # Stop the previous thread if it's running
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_stop_event.set()
            self.processing_thread.join()

        # Start a new thread
        self.processing_queue = Queue()
        self.processing_stop_event.clear()
        self.processing_thread = threading.Thread(
            target=task_processamento,
            args=(self.processing_stop_event, self.processing_queue),
            daemon=True,
        )
        self.processing_thread.start()

        # Watch the queue for new items
        self.after(100, self.watch_queue)

    def watch_queue(self):
        """
        Watch the processing queue for new items.
        This method can be used to update the UI or perform actions based on the queue.
        """

        # Read from the queue without blocking
        try:
            acessos_ids = self.processing_queue.get_nowait()

            # TODO: Fire an event instead of directly calling the frame method...
            if not acessos_ids:
                logger.debug(f"Received {len(acessos_ids)} access IDs from the queue")
                self.frames["Acessos"].update_sync_status(acessos_ids)
        except Empty:
            pass
        finally:
            self.after(100, self.watch_queue)  # Continue watching the queue

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

        # Stop the processing thread
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_stop_event.set()
            self.processing_thread.join()

        # Stop the Tray Icon thread
        if self.tray_icon:
            self.tray_icon.stop()

        # Destroy the window
        self.destroy()

    def run(self):
        self.mainloop()


if __name__ == "__main__":
    configure_logger()
    configure_database()

    app = App()
    app.run()
