import logging

from decouple import config
from rich.logging import RichHandler


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
