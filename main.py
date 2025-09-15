import logging
import threading
from datetime import datetime
from queue import Empty, Queue

import ttkbootstrap as ttk
from PIL import Image
from pystray import Icon, Menu, MenuItem

from topsoft.config import configure_logger
from topsoft.database import configure_database
from topsoft.frames import (
    AcessosFrame,
    CartoesAcessoFrame,
    ConfigurationFrame,
    TaskMonitorFrame,
)
from topsoft.tasks import task_db_processor, task_db_sync, task_file_reader
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
            "Monitor de Tarefas": TaskMonitorFrame(self.notebook, controller=self),
            "Configurações": ConfigurationFrame(self.notebook, controller=self),
        }

        for name, frame in self.frames.items():
            self.notebook.add(frame, text=name)

        # Notebook:
        self.notebook.pack(expand=True, fill="both")

        # Processamento:
        self.processing_queue = None
        self.file_reader_thread = None
        self.db_processor_thread = None
        self.db_sync_thread = None
        self.processing_stop_event = threading.Event()

        # Task status tracking
        self.task_status = {
            "file_reader": {
                "state": "stopped",
                "start_time": None,
                "details": "Aguardando inicialização...",
            },
            "db_processor": {
                "state": "stopped",
                "start_time": None,
                "details": "Aguardando inicialização...",
            },
            "db_sync": {
                "state": "stopped",
                "start_time": None,
                "details": "Aguardando inicialização...",
            },
        }

        self.start_processing_threads()

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

    def start_processing_threads(self):
        """
        Start the file reader, database processor, and API sync tasks in separate threads.
        """

        # Stop the previous threads if they're running
        if self.file_reader_thread and self.file_reader_thread.is_alive():
            self.processing_stop_event.set()
            self.file_reader_thread.join()
        if self.db_processor_thread and self.db_processor_thread.is_alive():
            self.processing_stop_event.set()
            self.db_processor_thread.join()
        if self.db_sync_thread and self.db_sync_thread.is_alive():
            self.processing_stop_event.set()
            self.db_sync_thread.join()

        # Start new threads
        self.processing_queue = Queue()
        self.processing_stop_event.clear()

        self.file_reader_thread = threading.Thread(
            target=task_file_reader,
            args=(self.processing_stop_event, self.processing_queue),
            daemon=True,
        )
        self.db_processor_thread = threading.Thread(
            target=task_db_processor,
            args=(self.processing_stop_event, self.processing_queue),
            daemon=True,
        )
        self.db_sync_thread = threading.Thread(
            target=task_db_sync,
            args=(self.processing_stop_event, self.processing_queue),
            daemon=True,
        )

        self.file_reader_thread.start()
        self.db_processor_thread.start()
        self.db_sync_thread.start()

        # Update task status to running
        from datetime import datetime

        now = datetime.now()
        self.task_status["file_reader"].update(
            {
                "state": "running",
                "start_time": now,
                "details": "Lendo arquivo bilhetes.txt...",
            }
        )
        self.task_status["db_processor"].update(
            {
                "state": "waiting",
                "start_time": now,
                "details": "Aguardando eventos para processar...",
            }
        )
        self.task_status["db_sync"].update(
            {
                "state": "running",
                "start_time": now,
                "details": "Sincronizando com API...",
            }
        )

        # Watch the queue for new items
        self.after(100, self.watch_queue)

    def get_task_status(self):
        """
        Get the current status of all tasks.
        """
        # Update status based on thread states
        if self.file_reader_thread and self.file_reader_thread.is_alive():
            if self.task_status["file_reader"]["state"] == "stopped":
                self.task_status["file_reader"].update(
                    {"state": "running", "details": "Lendo arquivo bilhetes.txt..."}
                )
        else:
            self.task_status["file_reader"].update(
                {"state": "stopped", "details": "Thread parada"}
            )

        if self.db_processor_thread and self.db_processor_thread.is_alive():
            if self.task_status["db_processor"]["state"] == "stopped":
                self.task_status["db_processor"].update(
                    {
                        "state": "waiting",
                        "details": "Aguardando eventos para processar...",
                    }
                )
        else:
            self.task_status["db_processor"].update(
                {"state": "stopped", "details": "Thread parada"}
            )

        if self.db_sync_thread and self.db_sync_thread.is_alive():
            if self.task_status["db_sync"]["state"] == "stopped":
                self.task_status["db_sync"].update(
                    {"state": "running", "details": "Sincronizando com API..."}
                )
        else:
            self.task_status["db_sync"].update(
                {"state": "stopped", "details": "Thread parada"}
            )

        return self.task_status

    def update_task_status(self, task_id, state, details=""):
        """
        Update the status of a specific task.
        """
        if task_id in self.task_status:
            self.task_status[task_id].update(
                {
                    "state": state,
                    "details": details,
                    "start_time": self.task_status[task_id].get(
                        "start_time", datetime.now()
                    ),
                }
            )

            # Also update the monitor frame if it exists
            if "Monitor de Tarefas" in self.frames:
                monitor_frame = self.frames["Monitor de Tarefas"]
                if hasattr(monitor_frame, "set_task_status"):
                    monitor_frame.set_task_status(task_id, state, details)

    def watch_queue(self):
        """
        Watch the processing queue for new items.
        This method can be used to update the UI or perform actions based on the queue.
        """

        # Read from the queue without blocking
        try:
            message = self.processing_queue.get_nowait()

            # Handle different message types
            if isinstance(message, tuple) and len(message) == 2:
                message_type, data = message

                if message_type == "SYNC_COMPLETED":
                    # Handle synced access records
                    logger.debug(
                        f"Received {len(data)} synced access IDs from the queue"
                    )
                    self.frames["Acessos"].update_sync_status(data)

                elif message_type == "TASK_STATUS":
                    # Handle task status updates
                    if isinstance(data, tuple) and len(data) == 3:
                        task_id, state, details = data
                        self.update_task_status(task_id, state, details)

            # Legacy support for old format (direct list of IDs)
            elif isinstance(message, list):
                logger.debug(f"Received {len(message)} access IDs from the queue")
                self.frames["Acessos"].update_sync_status(message)

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

        # Stop all processing threads
        if self.file_reader_thread and self.file_reader_thread.is_alive():
            self.processing_stop_event.set()
            self.file_reader_thread.join()
        if self.db_processor_thread and self.db_processor_thread.is_alive():
            self.processing_stop_event.set()
            self.db_processor_thread.join()
        if self.db_sync_thread and self.db_sync_thread.is_alive():
            self.processing_stop_event.set()
            self.db_sync_thread.join()

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
