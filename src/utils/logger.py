import logging
import sys

from config.settings import settings


def _setup_logger() -> logging.Logger:
    log = logging.getLogger("pineclaw")
    log.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] %(levelname)s %(name)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        log.addHandler(handler)

    return log


logger = _setup_logger()
