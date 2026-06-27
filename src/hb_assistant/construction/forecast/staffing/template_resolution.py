"""Template-inheritance / effective-row resolution (Phase 2a).

A staffing config row may derive defaults from a global template version. For each inheritable
field the *effective* value is the config row's own value when the field is listed in
``override_fields`` (or the row has no template); otherwise the template version's default. Fields
not listed below (person_name, dates, project identity) are always taken from the config row.
"""

from __future__ import annotations

import json
from typing import Any

# config field -> template-version default field
INHERITABLE_FIELDS: dict[str, str] = {
    "role_title": "default_role_title",
    "employment_type": "default_employment_type",
    "rate_unit": "default_rate_unit",
    "cost_code": "cost_code",
    "cost_code_description": "cost_code_description",
    "lab_rate": "default_lab_rate",
    "lbn_rate": "default_lbn_rate",
    "mat_rate": "default_mat_rate",
}


class TemplateResolutionError(RuntimeError):
    """A config row references a template that has no resolvable version (a blocking input)."""


def _override_set(config_row: dict[str, Any]) -> set[str]:
    raw = config_row.get("override_fields")
    if raw is None:
        raw = config_row.get("override_fields_json")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            raw = []
    return set(raw or [])


def resolve_effective_row(
    config_row: dict[str, Any], template_version: dict[str, Any] | None
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Return (effective_row, inherited_fields, overridden_fields).

    Raises ``TemplateResolutionError`` when the row has a ``template_id`` but no template version
    was resolved.
    """
    effective = dict(config_row)
    has_template = bool(config_row.get("template_id"))
    if has_template and template_version is None:
        raise TemplateResolutionError(
            f"template {config_row.get('template_id')} has no resolvable version"
        )

    overrides = _override_set(config_row)
    inherited: list[str] = []
    overridden: list[str] = []

    if not has_template:
        # Standalone row: its own values are authoritative; nothing inherited.
        return effective, inherited, overridden

    assert template_version is not None
    for field, default_field in INHERITABLE_FIELDS.items():
        if field in overrides:
            overridden.append(field)
            # keep the config row's own value
        else:
            effective[field] = template_version.get(default_field)
            inherited.append(field)
    return effective, sorted(inherited), sorted(overridden)
