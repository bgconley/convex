"""Structured JSON logging for Cortex.

Configures Python's logging module to emit JSON-formatted log lines
with consistent fields: timestamp, level, logger, message, and optional
extras (request_id, document_id, etc.).

Usage:
    from cortex.infrastructure.logging import configure_logging
    configure_logging(level="INFO", json_format=True)
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone

# Context variable for request correlation ID
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None,
)


class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc,
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Attach correlation ID if present
        req_id = request_id_var.get()
        if req_id:
            log_entry["request_id"] = req_id

        # Attach any extra fields set via logger.info("msg", extra={...})
        for key in ("document_id", "query", "duration_ms", "status_code", "method", "path"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def configure_logging(level: str = "INFO", json_format: bool = True) -> None:
    """Configure root logger with JSON or plain text formatter.

    Call once at startup (both API and Celery worker).
    """
    root = logging.getLogger()
    root.setLevel(level.upper())

    # Remove existing handlers (e.g., Uvicorn defaults)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level.upper())

    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )

    root.addHandler(handler)

    # Quiet noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
