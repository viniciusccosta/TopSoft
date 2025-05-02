import logging
import sys
from os import path

import toml

logger = logging.getLogger(__name__)


def get_path(filename):
    """
    Get the correct path for a file, whether running in development or as a PyInstaller executable.
    """
    if hasattr(sys, "_MEIPASS"):
        return path.realpath(path.join(sys._MEIPASS, filename))
    return filename


def get_current_version():
    """
    Get the current version of the application from pyproject.toml.
    """
    try:
        with open("pyproject.toml", "r", encoding="utf-8") as f:
            pyproject_data = toml.load(f)
            return pyproject_data.get("project", {}).get("version", "0.0.0")
    except FileNotFoundError:
        logger.error("pyproject.toml not found")
    except Exception as e:
        logger.error(f"Error reading pyproject.toml: {e}")

    return "0.0.0"
