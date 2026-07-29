"""Contact projection field registry."""

from __future__ import annotations

CONTACT_PROJECTION_SCHEMA_VERSION = "apple_contact_projection_v1"

# Non-PII projection fields only (counts/flags). Raw PII stays in raw tables.
CONTACT_PROJECTION_FIELDS: tuple[str, ...] = (
    "contact_type",
    "has_email",
    "has_phone",
    "email_count",
    "phone_count",
    "source_quality",
    "projection_schema_version",
    "projected_utc",
)


def required_fields() -> frozenset[str]:
    return frozenset(CONTACT_PROJECTION_FIELDS)
