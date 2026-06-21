"""Column + budget-code mapping for external-forecast evaluation (Implementation Phase 4).

Two facets, both deterministic and pure:

1. **Column roles** — propose which uploaded columns are the budget code / month / value / EAC /
   remaining, by header-name heuristics; the operator can override.
2. **Budget-code normalization** — match each raw code label to a canonical v59 budget-code key
   (exact normalized match). No match -> ``unmapped``; a normalized form that collides with more
   than one canonical key -> ``ambiguous``. When no canonical set is available (no baseline DB),
   raw codes are accepted as-is with status ``unverified`` so the pipeline still runs.
"""

from __future__ import annotations

import re
from typing import Any

from hb_assistant.construction.analytics.forecast_external_baselines import (
    load_canonical_budget_codes,
    resolve_db_path,
)
from hb_assistant.construction.analytics.forecast_external_dto import (
    MappingProposalDTO,
    MappingRowDTO,
)
from hb_assistant.construction.analytics.forecast_external_ingest import (
    ForecastExternalIngestService,
)

ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "budget_code": ("budget code", "cost code", "code", "budget"),
    "month": ("month", "period", "date"),
    "eac": ("eac", "estimate at completion", "final cost", "at completion"),
    "remaining": ("remaining", "etc", "to complete", "cost to complete"),
    "value": ("forecast", "value", "amount", "projected"),
}
ROLE_ORDER = ("budget_code", "month", "eac", "remaining", "value")


def _norm_code(label: object) -> str:
    return re.sub(r"[^0-9a-z]", "", str(label or "").lower())


def propose_column_roles(columns: list[str]) -> dict[str, str]:
    """Best-effort header -> role guess. Each column is assigned at most one (most specific) role."""
    roles: dict[str, str] = {}
    used: set[str] = set()
    for role in ROLE_ORDER:
        for col in columns:
            if col in used:
                continue
            low = col.lower()
            if any(kw in low for kw in ROLE_KEYWORDS[role]):
                roles[role] = col
                used.add(col)
                break
    return roles


class ForecastExternalMappingService:
    """Proposes and validates the column + budget-code mapping for an imported external forecast."""

    def __init__(
        self,
        eval_root: str | None = None,
        db_path: str | None = None,
    ) -> None:
        self._ingest = ForecastExternalIngestService(eval_root=eval_root)
        self._db_path_override = db_path

    def _canonical_codes(self, project_key: str) -> set[str]:
        return load_canonical_budget_codes(resolve_db_path(self._db_path_override), project_key)

    def propose_mapping(self, import_id: str, project_key: str = "tropical") -> dict[str, Any]:
        record = self._ingest.read_import_record(import_id)
        columns = list(record.get("columns") or [])
        roles = propose_column_roles(columns)
        rows = self._ingest.read_parsed_rows(import_id)
        canonical = self._canonical_codes(project_key)
        code_col = roles.get("budget_code")
        raw_labels = self._distinct_raw_codes(rows, code_col)
        mapping_rows = [self._classify_code(label, canonical) for label in raw_labels]
        mapped = sum(1 for r in mapping_rows if r.mapping_status in ("mapped", "unverified"))
        unmapped = len(mapping_rows) - mapped
        proposal = MappingProposalDTO(
            import_id=import_id,
            mapped_count=mapped,
            unmapped_count=unmapped,
            rows=mapping_rows,
        )
        out = proposal.public()
        out["proposed_column_roles"] = roles
        out["columns"] = columns
        return out

    def validate_mapping(
        self,
        import_id: str,
        column_roles: dict[str, str],
        project_key: str = "tropical",
    ) -> dict[str, Any]:
        """Apply column roles to the parsed rows -> normalized external rows + mapped/unmapped split."""
        if not column_roles.get("budget_code"):
            raise _mapping_error("a budget-code column must be mapped")
        if not (column_roles.get("value") or column_roles.get("eac")):
            raise _mapping_error("a value or EAC column must be mapped")
        rows = self._ingest.read_parsed_rows(import_id)
        canonical = self._canonical_codes(project_key)
        code_col = column_roles["budget_code"]
        norm_to_canonical = self._normalized_canonical_index(canonical)

        mapped_rows: list[dict[str, Any]] = []
        unmapped_rows: list[dict[str, Any]] = []
        for order, row in enumerate(rows):
            raw_label = str(row.get(code_col, "")).strip()
            status, canonical_key, confidence = self._resolve_code(
                raw_label, canonical, norm_to_canonical
            )
            normalized = {
                "raw_label": raw_label,
                "budget_code_key": canonical_key or raw_label,
                "month": _cell(row, column_roles.get("month")),
                "value": _cell(row, column_roles.get("value")),
                "eac": _cell(row, column_roles.get("eac")),
                "remaining": _cell(row, column_roles.get("remaining")),
                "confidence": confidence,
                "mapping_status": status,
                "row_order": order,
            }
            if status in ("mapped", "unverified"):
                mapped_rows.append(normalized)
            else:
                unmapped_rows.append(normalized)
        return {
            "import_id": import_id,
            "column_roles": column_roles,
            "mapped_rows": mapped_rows,
            "unmapped_rows": unmapped_rows,
            "mapped_count": len(mapped_rows),
            "unmapped_count": len(unmapped_rows),
            "canonical_available": bool(canonical),
        }

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _distinct_raw_codes(rows: list[dict[str, Any]], code_col: str | None) -> list[str]:
        if not code_col:
            return []
        seen: dict[str, None] = {}
        for row in rows:
            label = str(row.get(code_col, "")).strip()
            if label:
                seen.setdefault(label, None)
        return list(seen)

    @staticmethod
    def _normalized_canonical_index(canonical: set[str]) -> dict[str, list[str]]:
        idx: dict[str, list[str]] = {}
        for key in canonical:
            idx.setdefault(_norm_code(key), []).append(key)
        return idx

    def _classify_code(self, label: str, canonical: set[str]) -> MappingRowDTO:
        status, canonical_key, confidence = self._resolve_code(
            label, canonical, self._normalized_canonical_index(canonical)
        )
        return MappingRowDTO(
            raw_label=label,
            canonical_budget_code_key=canonical_key,
            canonical_month=None,
            mapping_confidence=confidence,
            mapping_status=status,
        )

    @staticmethod
    def _resolve_code(
        label: str, canonical: set[str], norm_index: dict[str, list[str]]
    ) -> tuple[str, str | None, str | None]:
        if not canonical:
            # No canonical set available: accept the raw label, flag as unverified.
            return ("unverified", label or None, "unverified") if label else ("unmapped", None, None)
        if label in canonical:
            return "mapped", label, "exact"
        matches = norm_index.get(_norm_code(label), [])
        if len(matches) == 1:
            return "mapped", matches[0], "normalized"
        if len(matches) > 1:
            return "ambiguous", None, None
        return "unmapped", None, None


def _cell(row: dict[str, Any], col: str | None) -> Any:
    if not col:
        return None
    val = row.get(col)
    return None if val == "" else val


def _mapping_error(msg: str) -> Exception:
    from hb_assistant.construction.analytics.forecast_external_ingest import ForecastExternalError

    return ForecastExternalError(msg)
