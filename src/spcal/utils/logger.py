import logging
import os
from datetime import datetime
from typing import Union


def _normalize_level(level: Union[int, str, None]) -> int:
    """
    Accepts int or str (e.g. 'DEBUG', 'info', '20') and returns a logging level int.
    Defaults to logging.INFO.
    """
    if isinstance(level, int):
        return level
    if isinstance(level, str):
        s = level.strip().upper()
        # numeric string?
        if s.isdigit():
            try:
                return int(s)
            except ValueError:
                pass
        # named level
        return logging._nameToLevel.get(s, logging.INFO)
    return logging.INFO


def setup_logger(
    name: str = "global", level: Union[int, str, None] = None
) -> logging.Logger:
    """
    Create (or reuse) a logger that logs to both file and console.
    The log format includes filename, line number, and function name.
    """
    # Resolve level from env first, then param
    env_level = os.environ.get("LOG_LEVEL", None)
    eff_level = _normalize_level(level if level is not None else env_level)

    # Compute project dir and log dir
    project_dir = os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../")
    )
    log_dir = os.path.join(project_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"{timestamp}.log")

    logger = logging.getLogger(name)
    logger.setLevel(eff_level)
    # avoid duplicate propagation to root
    logger.propagate = False

    # If handlers already exist (module re-import), just update their level/formatter and return.
    if logger.handlers:
        for h in logger.handlers:
            h.setLevel(eff_level)
            h.setFormatter(_default_formatter())
        return logger

    # File handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(eff_level)
    fh.setFormatter(_default_formatter())
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(eff_level)
    ch.setFormatter(_default_formatter())
    logger.addHandler(ch)

    return logger


def _default_formatter() -> logging.Formatter:
    """
    Default formatter showing timestamp, level, filename, line, function, and message.
    Example:
    2025-10-26 12:34:56 [INFO] cell_iterator.py:123 run | Finished. Summary: {...}
    """
    fmt = (
        "%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d %(funcName)s | %(message)s"
    )
    datefmt = "%Y-%m-%d %H:%M:%S"
    return logging.Formatter(fmt=fmt, datefmt=datefmt)


# Export a ready-to-use logger (so you can `from spcal.utils.logger import logger`)
logger = setup_logger("global")
