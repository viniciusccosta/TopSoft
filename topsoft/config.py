import logging
from logging.handlers import RotatingFileHandler

from decouple import config
from rich.logging import RichHandler


def configure_logger():
    """
    Configure the logger for the application with log rotation.
    """

    log_level = config("LOGGING_LEVEL", default=logging.INFO)

    # Log rotation configuration
    max_log_size = config("MAX_LOG_SIZE_MB", default=50, cast=int) * 1024 * 1024  # Convert MB to bytes
    backup_count = config("LOG_BACKUP_COUNT", default=5, cast=int)

    # Handlers with rotation:
    file_handler = RotatingFileHandler("topsoft.log", maxBytes=max_log_size, backupCount=backup_count, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s"))

    console_handler = RichHandler(rich_tracebacks=True)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter("%(name)s - %(funcName)s - %(message)s"))

    # Suppress third-party libraries logging:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("rich").setLevel(logging.WARNING)
    logging.getLogger("pygtail").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("win32ctypes").setLevel(logging.WARNING)
    logging.getLogger("keyring").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Logger:
    logging.basicConfig(
        level=log_level,
        handlers=[console_handler, file_handler],
    )
