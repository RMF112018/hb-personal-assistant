"""XER schedule parser adapter (deferred implementation)."""

from __future__ import annotations

from .schedule_file_parser import ParsedScheduleBundle, ScheduleImportError

PARSER_NAME = "schedule_xer_parser"
PARSER_VERSION = "0.0.0-stub"


def parse_xer_bytes(data: bytes) -> ParsedScheduleBundle:
    raise ScheduleImportError(
        "unsupported_schedule_format",
        message="xer_parser_not_available",
    )