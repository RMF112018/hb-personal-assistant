"""Per-endpoint normalization modules for Procore canonical records.

Each normalizer is a pure function: no I/O, no network, no globals beyond
imports. Callers stamp ``fetched_at`` and supply ``correlation_id``. Output
is a plain ``dict`` that mirrors the row shape consumed by
:func:`hb_assistant.store.repositories.upsert_procore_synced_entity`.

Phase 04 Prompt 04 introduces RFI normalization; subsequent prompts add
Submittal / Observation / Meeting / Daily Log normalizers that mirror this
contract.
"""

from .daily_log import (
    normalize_daily_log_payload_block,
    normalize_daily_log_section_item,
)
from .inspection import (
    normalize_inspection,
    normalize_inspection_item,
    normalize_inspection_section,
)
from .meeting import (
    extract_topics_from_categories,
    normalize_meeting,
    normalize_meeting_detail,
    normalize_meeting_payload_block,
    normalize_meeting_topic,
    normalize_meeting_topic_payload_block,
)
from .observation import (
    normalize_observation,
    normalize_observation_comment,
    normalize_observation_payload_block,
)
from .punch_item import (
    normalize_punch_item,
)
from .rfi import (
    NORMALIZATION_SCHEMA_VERSION,
    normalize_rfi,
    normalize_rfi_payload_block,
    normalize_rfi_reply,
)
from .schedule import (
    normalize_activity,
    normalize_schedule,
)
from .submittal import (
    normalize_submittal,
    normalize_submittal_package,
    normalize_submittal_payload_block,
    normalize_submittal_response,
)

__all__ = [
    "NORMALIZATION_SCHEMA_VERSION",
    "normalize_daily_log_payload_block",
    "normalize_daily_log_section_item",
    "extract_topics_from_categories",
    "normalize_meeting",
    "normalize_meeting_detail",
    "normalize_meeting_payload_block",
    "normalize_meeting_topic",
    "normalize_meeting_topic_payload_block",
    "normalize_activity",
    "normalize_inspection",
    "normalize_inspection_item",
    "normalize_inspection_section",
    "normalize_observation",
    "normalize_observation_comment",
    "normalize_observation_payload_block",
    "normalize_punch_item",
    "normalize_rfi",
    "normalize_schedule",
    "normalize_rfi_payload_block",
    "normalize_rfi_reply",
    "normalize_submittal",
    "normalize_submittal_package",
    "normalize_submittal_payload_block",
    "normalize_submittal_response",
]
