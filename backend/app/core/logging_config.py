import logging
import sys


def setup_logging(debug: bool = False) -> None:
    """Configure application-wide logging."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    # Quieter third-party loggers unless debug mode
    if not debug:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
