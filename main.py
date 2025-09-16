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
from topsoft.tasks import DatabaseProcessorTask, DatabaseSyncTask, FileReaderTask
from topsoft.utils import get_path

logger = logging.getLogger(__name__)


class App(ttk.Window):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Window:
        self.title("TopSoft")
        self.geometry("800x800")

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

        # Initialize task monitoring objects
        self._initialize_tasks()

        # Task status tracking
        self.start_processing_threads()

        # System Tray:
        self.tray_icon = None
        self.create_tray_icon()

    def _initialize_tasks(self):
        """Initialize the monitored task objects."""
        self.file_reader_task = FileReaderTask()
        self.db_processor_task = DatabaseProcessorTask()
        self.db_sync_task = DatabaseSyncTask()

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

        # Start new threads - use the task classes directly
        self.processing_queue = Queue()
        self.processing_stop_event.clear()

        # Pass the queue and stop_event to the tasks and start them
        self.file_reader_thread = self.file_reader_task.start(
            self.processing_stop_event, self.processing_queue
        )
        self.db_processor_thread = self.db_processor_task.start(
            self.processing_stop_event, self.processing_queue
        )
        self.db_sync_thread = self.db_sync_task.start(
            self.processing_stop_event, self.processing_queue
        )

        # Watch the queue for new items
        self.after(100, self.watch_queue)

    def watch_queue(self):
        """
        Watch the processing queue for new items.
        Now only handles data updates (sync status and new records).
        Task status updates are handled through the task registry.
        """

        # Process all available messages in the queue
        messages_processed = 0
        while True:
            try:
                message = self.processing_queue.get_nowait()
                messages_processed += 1

                # Handle different message types
                if isinstance(message, tuple) and len(message) == 2:
                    message_type, data = message

                    if message_type == "SYNC_COMPLETED":
                        # Handle synced access records
                        logger.debug(
                            f"Received {len(data)} synced access IDs from the queue"
                        )
                        self.frames["Acessos"].update_sync_status(data)

                    elif message_type == "DATA_PROCESSED":
                        # Handle new data processed into database
                        logger.debug(
                            f"Received notification of {data} new records processed"
                        )
                        self.frames["Acessos"].handle_new_data_processed(data)

                    # TASK_STATUS messages are no longer needed - tasks update themselves

                # Legacy support for old format (direct list of IDs)
                elif isinstance(message, list):
                    logger.debug(f"Received {len(message)} access IDs from the queue")
                    self.frames["Acessos"].update_sync_status(message)

            except Empty:
                # No more messages in queue, break the loop
                break

        if messages_processed > 0:
            logger.debug(f"Processed {messages_processed} messages from queue")

        # Continue watching the queue
        self.after(100, self.watch_queue)

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
        Handle the exit event with proper cleanup.
        """
        logger.info("Application exit requested")

        # Stop all processing threads
        self.processing_stop_event.set()

        # Wait for threads to finish with timeout
        threads_to_wait = [
            ("file_reader", self.file_reader_thread),
            ("db_processor", self.db_processor_thread),
            ("db_sync", self.db_sync_thread),
        ]

        for thread_name, thread in threads_to_wait:
            if thread and thread.is_alive():
                logger.info(f"Waiting for {thread_name} thread to finish...")
                thread.join(timeout=3.0)  # Wait up to 3 seconds per thread

                if thread.is_alive():
                    logger.warning(
                        f"{thread_name} thread did not respond to stop signal in time"
                    )
                else:
                    logger.info(f"{thread_name} thread stopped successfully")

        # Stop the Tray Icon thread
        if self.tray_icon:
            try:
                self.tray_icon.stop()
                logger.info("Tray icon stopped")
            except Exception as e:
                logger.error(f"Error stopping tray icon: {e}")

        # Destroy the window
        try:
            self.destroy()
            logger.info("Application closed successfully")
        except Exception as e:
            logger.error(f"Error destroying main window: {e}")
            # Force exit if normal cleanup fails
            import sys

            sys.exit(1)

    def run(self):
        self.mainloop()


if __name__ == "__main__":
    configure_logger()
    configure_database()

    app = App()
    app.run()
