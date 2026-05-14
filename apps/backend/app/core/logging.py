import sys
from typing import Any

from loguru import logger


def configure_logging(debug: bool) -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        level="DEBUG" if debug else "INFO",
        serialize=True,
        backtrace=debug,
        diagnose=debug,
    )


def bind_correlation_id(correlation_id: str) -> Any:
    return logger.bind(correlation_id=correlation_id)

