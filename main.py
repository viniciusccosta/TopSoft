import logging
import threading

import ttkbootstrap as ttk

from topsoft.frames import ConfigurationFrame, MainFrame
from topsoft.tasks import background_task


class App(ttk.Window):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("TopSoft")
        # self.geometry("800x600")

        # Notebook
        self.notebook = ttk.Notebook(self)

        # Frames:
        self.frames = {
            "TopSoft": MainFrame(self.notebook),
            "Configurações": ConfigurationFrame(self.notebook),
        }

        for name, frame in self.frames.items():
            self.notebook.add(frame, text=name)

        # Notebook
        self.notebook.pack(expand=True, fill="both")

        # Start background tasks
        # TODO: read interval from config/database
        self.thread = threading.Thread(target=background_task, args=(60,))
        self.thread.daemon = True
        self.thread.start()

    def run(self):
        self.mainloop()


if __name__ == "__main__":
    # TODO: SystemTray icon
    # TODO: Auto launch on startup
    # TODO: Auto check for updates
    # TODO: Create database
    # TODO: Create installation file

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    app = App()
    app.run()
