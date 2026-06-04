"""Structured logging configuration using structlog."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog

from src.config import settings


def setup_logging() -> None:
    """Configure structured logging with structlog + stdlib logging."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    settings.log_dir.mkdir(parents=True, exist_ok=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging for third-party libs
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        handlers=[
            logging.StreamHandler(sys.stderr),
            logging.FileHandler(settings.log_dir / "svtr.log"),
        ],
    )

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("ccxt").setLevel(logging.WARNING)
