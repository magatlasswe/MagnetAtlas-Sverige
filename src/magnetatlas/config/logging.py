"""Central logging configuration."""

from __future__ import annotations

import logging

from rich.logging import RichHandler


def configure_logging(level: str = "INFO") -> None:
    """Configure application logging with Rich terminal output."""
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, markup=False)],
        force=True,
    )
