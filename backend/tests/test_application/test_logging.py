"""Tests for structured logging configuration."""

from __future__ import annotations

import json
import logging

from cortex.infrastructure.logging import (
    JSONFormatter,
    configure_logging,
    request_id_var,
)


class TestJSONFormatter:
    def test_basic_format(self) -> None:
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Hello %s",
            args=("world",),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "Hello world"
        assert "timestamp" in parsed

    def test_request_id_included(self) -> None:
        formatter = JSONFormatter()
        token = request_id_var.set("abc123")
        try:
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg="test", args=(), exc_info=None,
            )
            output = formatter.format(record)
            parsed = json.loads(output)
            assert parsed["request_id"] == "abc123"
        finally:
            request_id_var.reset(token)

    def test_extra_fields(self) -> None:
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test", args=(), exc_info=None,
        )
        record.document_id = "doc-123"
        record.duration_ms = 42.5
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["document_id"] == "doc-123"
        assert parsed["duration_ms"] == 42.5

    def test_no_request_id_when_unset(self) -> None:
        formatter = JSONFormatter()
        token = request_id_var.set(None)
        try:
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg="test", args=(), exc_info=None,
            )
            output = formatter.format(record)
            parsed = json.loads(output)
            assert "request_id" not in parsed
        finally:
            request_id_var.reset(token)


class TestConfigureLogging:
    def test_json_mode(self) -> None:
        configure_logging(level="DEBUG", json_format=True)
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JSONFormatter)

    def test_plain_mode(self) -> None:
        configure_logging(level="WARNING", json_format=False)
        root = logging.getLogger()
        assert root.level == logging.WARNING
        assert len(root.handlers) == 1
        assert not isinstance(root.handlers[0].formatter, JSONFormatter)
