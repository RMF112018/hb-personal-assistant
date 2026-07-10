"""Canonical skip-code vocabulary for source-intelligence queue events.

A skip is a *clean* terminal state of a ``source_intelligence_events`` row (status='skipped') —
NOT an error. The ``error_code`` column carries a named reason so the operator status rollup
(``skipped_by_code``) is meaningful rather than a wall of ``unspecified``.

Two distinct "unspecified" buckets exist on purpose:

* ``unspecified`` — legacy/historical skip rows written before skip-code normalization, where
  ``error_code`` is NULL. ``index_status`` coalesces NULL → ``"unspecified"`` at READ time only.
* ``unspecified_skip`` (``UNSPECIFIED_SKIP``) — the canonical fallback stamped at the WRITE boundary
  (``complete_event``) when a *new* skip path forgets to pass a code. Its presence in
  ``skipped_by_code`` is a regression signal (a new code-less skip), cleanly distinguishable from the
  legacy NULL bucket above.

This module has NO dependencies (importable from the repository, indexer, and value classifier
without an import cycle).
"""

from __future__ import annotations

# Stamped at the complete_event write boundary when a new skip omits a code (regression signal).
UNSPECIFIED_SKIP = "unspecified_skip"

# Named, expected skip reasons. Every NEW skip path should pass one of these.
EXCLUDED_PATH = "excluded_path"
DEFERRED_PATH = "deferred_path"
METADATA_ONLY_NO_AUTO_CARD = "metadata_only_no_auto_card"
UNSUPPORTED_FILE_TYPE = "unsupported_file_type"
TEMPORARY_FILE = "temporary_file"
SOURCE_NOTES_SELF_INDEX_GUARD = "source_notes_self_index_guard"
EMAIL_ARCHIVE_SELF_INDEX_GUARD = "email_archive_self_index_guard"
DELETED_SOURCE = "deleted_source"
NOT_ENABLED = "not_enabled"
OUTSIDE_ROOT = "outside_root"
TOO_LARGE = "too_large"
EXTRACTION_UNSUPPORTED = "extraction_unsupported"
EXTRACTION_FAILED = "extraction_failed"
# A bounded rebuild pass stopped early (max_files_per_pass/max_seconds) with work remaining. The event
# is completed as a clean ``skipped`` receipt (NOT an error) and a coalesced replacement ``rebuild`` event
# is enqueued so the remainder resumes on the next drain — the queue status vocabulary is unchanged.
BOUNDED_RESUME = "bounded_resume"

# The full canonical vocabulary (the fallback included). Used to validate/recognize codes.
SKIP_CODES: frozenset[str] = frozenset({
    EXCLUDED_PATH,
    DEFERRED_PATH,
    METADATA_ONLY_NO_AUTO_CARD,
    UNSUPPORTED_FILE_TYPE,
    TEMPORARY_FILE,
    SOURCE_NOTES_SELF_INDEX_GUARD,
    EMAIL_ARCHIVE_SELF_INDEX_GUARD,
    DELETED_SOURCE,
    NOT_ENABLED,
    OUTSIDE_ROOT,
    TOO_LARGE,
    EXTRACTION_UNSUPPORTED,
    EXTRACTION_FAILED,
    BOUNDED_RESUME,
    UNSPECIFIED_SKIP,
})


def normalize_skip_code(code: str | None) -> str:
    """Coalesce a skip ``error_code`` for the WRITE boundary.

    A missing/blank code becomes :data:`UNSPECIFIED_SKIP` (never NULL) so a new code-less skip is a
    visible regression rather than silently merging into the legacy NULL→``unspecified`` bucket. A
    non-empty code is preserved verbatim (codes stay free-form strings; this never rejects an
    unknown code — it only fills the empty case).
    """
    text = str(code).strip() if code is not None else ""
    return text or UNSPECIFIED_SKIP
