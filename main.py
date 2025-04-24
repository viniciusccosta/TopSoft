import logging
import threading

import ttkbootstrap as ttk
from rich.logging import RichHandler

from topsoft.frames import ConfigurationFrame, MainFrame
from topsoft.tasks import background_task


class App(ttk.Window):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Window:
        self.title("TopSoft")
        self.geometry("800x600")

        # Notebook
        self.notebook = ttk.Notebook(self)

        # Frames:
        self.frames = {
            "TopSoft": MainFrame(self.notebook, controller=self),
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

        # TODO: Ask for confirmation before closing

        self.stop_thread()
        self.destroy()

    def run(self):
        self.mainloop()


if __name__ == "__main__":
    # TODO: SystemTray icon
    # TODO: Auto launch on startup
    # TODO: Auto check for updates
    # TODO: Create installation file

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
            )
        ],
    )

    app = App()
    app.run()
