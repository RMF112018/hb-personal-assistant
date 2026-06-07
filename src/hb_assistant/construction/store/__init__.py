"""Construction-agent store layer (metadata-only persistence)."""

from .repositories import CalendarBatchApplyError, ConstructionStore, EmailDiscoverBatchApplyError

# Phase 10A: email raw list/get accessors (list_email_message_raw_content,
# get_email_message_raw_content, list_email_thread_raw_context,
# get_email_thread_raw_context) are instance methods on ConstructionStore
# (symmetric to the calendar raw ones added in Prompt 04). They are
# surfaced automatically via the ConstructionStore import.
__all__ = ["CalendarBatchApplyError", "ConstructionStore", "EmailDiscoverBatchApplyError"]
