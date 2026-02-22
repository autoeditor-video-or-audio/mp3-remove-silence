import logging
import sys

from app.config import LOG_LEVEL


def setup_logger():
    fmt = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)

    return logging.getLogger(__name__)
