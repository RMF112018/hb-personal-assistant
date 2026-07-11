"""Central typed-ID parser for prompt routing and gateway argument validation.

Versioned, anchored patterns preserve exact ID values (no truncation or normalization).
Used by prompt_preflight, pa_prompt_route, and hb_assistant_tool_query argument hygiene.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

PARSER_VERSION = 1
_TYPED_CANONICAL_MAX_LEN = 48

_RETRIEVAL_VERB_RE = re.compile(
    r"\b(show(?:\s+me)?(?:\s+the)?|retrieve|get|open|display)\b",
    re.IGNORECASE,
)


class IdKind(StrEnum):
    DECISION = "decision"
    PREFERENCE = "preference"
    OPEN_LOOP = "open_loop"
    SESSION = "session"
    PROPOSAL = "proposal"
    PROPOSAL_BUNDLE = "proposal_bundle"
    PROMOTION_BUNDLE = "promotion_bundle"
    PROMOTION_RECEIPT = "promotion_receipt"
    OUTPUT = "output"
    SOURCE = "source"
    OPERATOR_APPROVAL = "operator_approval"
    CONTEXT_PACK = "context_pack"
    FEEDBACK = "feedback"
    QUALITY_RUN = "quality_run"
    ACTION_STAGE = "action_stage"
    RECEIPT_HASH = "receipt_hash"


class ValidationState(StrEnum):
    VALID = "valid"
    INVALID_SUFFIX = "invalid_suffix"
    PARTIAL_MATCH = "partial_match"
    OVERLONG = "overlong"
    CONFLICTING = "conflicting"


@dataclass(frozen=True)
class ParsedId:
    id_type: IdKind
    value: str
    validation_state: ValidationState
    source_span: tuple[int, int]
    target_tool: str | None = None
    arg_name: str | None = None


@dataclass
class IdParseResult:
    ids: list[ParsedId]
    by_arg: dict[str, list[ParsedId]]
    conflicts: list[str]

    def value_for_arg(self, arg_name: str) -> str | None:
        matches = self.by_arg.get(arg_name, [])
        valid = [m for m in matches if m.validation_state == ValidationState.VALID]
        if len(valid) != 1:
            return None
        return valid[0].value


# arg_name → (IdKind, optional target_tool)
_ARG_BINDINGS: dict[str, tuple[IdKind, str | None]] = {
    "decision_id": (IdKind.DECISION, "assistant_get_decision"),
    "preference_id": (IdKind.PREFERENCE, "assistant_get_preference"),
    "open_loop_id": (IdKind.OPEN_LOOP, "assistant_get_open_loop"),
    "session_id": (IdKind.SESSION, None),
    "proposal_id": (IdKind.PROPOSAL, "pa_artifact_proposal_get"),
    "proposal_bundle_id": (IdKind.PROPOSAL_BUNDLE, None),
    "promotion_bundle_id": (IdKind.PROMOTION_BUNDLE, "pa_artifact_promotion_apply"),
    "promotion_receipt_id": (IdKind.PROMOTION_RECEIPT, "pa_artifact_promotion_receipt_get"),
    "output_id": (IdKind.OUTPUT, "pa_output_metadata"),
    "receipt_id": (IdKind.RECEIPT_HASH, "pa_output_receipt_get"),
    "source_id": (IdKind.SOURCE, "assistant_source_file_read"),
    "operator_approval_id": (IdKind.OPERATOR_APPROVAL, None),
    "pack_id": (IdKind.CONTEXT_PACK, "assistant_get_context_pack"),
    "context_pack_id": (IdKind.CONTEXT_PACK, "assistant_get_context_pack"),
    "feedback_id": (IdKind.FEEDBACK, "assistant_get_feedback"),
    "quality_run_id": (IdKind.QUALITY_RUN, "assistant_get_quality"),
    "stage_id": (IdKind.ACTION_STAGE, "assistant_get_action_stage"),
}

# Patterns ordered most-specific first. Each entry: (IdKind, compiled regex, normalizer).
_ID_PATTERNS: list[tuple[IdKind, re.Pattern[str], Any]] = [
    # Canonical cards — must not be truncated.
    (
        IdKind.DECISION,
        re.compile(r"\b(DEC-\d{8}-[A-F0-9]{6})\b", re.IGNORECASE),
        lambda m: m.group(1).upper(),
    ),
    (
        IdKind.PREFERENCE,
        re.compile(r"\b(PREF-\d{8}-[A-F0-9]{6})\b", re.IGNORECASE),
        lambda m: m.group(1).upper(),
    ),
    (
        IdKind.OPEN_LOOP,
        re.compile(r"\b(LOOP-\d{8}-[A-F0-9]{6})\b", re.IGNORECASE),
        lambda m: m.group(1).upper(),
    ),
    # Dated sequential IDs — hyphenated suffix (fixes PROMOB-20260711-001 truncation).
    (
        IdKind.PROMOTION_BUNDLE,
        re.compile(r"\b(PROMOB-\d{8}-\d{3})\b", re.IGNORECASE),
        lambda m: m.group(1).upper(),
    ),
    (
        IdKind.PROMOTION_RECEIPT,
        re.compile(r"\b(PROMO-\d{8}-\d{3})\b", re.IGNORECASE),
        lambda m: m.group(1).upper(),
    ),
    (
        IdKind.PROPOSAL_BUNDLE,
        re.compile(r"\b(BUNDLE-\d{8}-\d{3})\b", re.IGNORECASE),
        lambda m: m.group(1).upper(),
    ),
    (
        IdKind.PROPOSAL,
        re.compile(r"\b(PROP-\d{8}-\d{3})\b", re.IGNORECASE),
        lambda m: m.group(1).upper(),
    ),
    (
        IdKind.SESSION,
        re.compile(r"\b(SESSION-\d{8}-\d{3})\b", re.IGNORECASE),
        lambda m: m.group(1).upper(),
    ),
    (
        IdKind.OUTPUT,
        re.compile(r"\b(OUTPUT-\d{8}-\d{3})\b", re.IGNORECASE),
        lambda m: m.group(1).upper(),
    ),
    # Short alphanumeric forms (audit corpus / legacy).
    (
        IdKind.PROMOTION_BUNDLE,
        re.compile(r"\b(PROMOB-[A-Z0-9]{6,16})\b"),
        lambda m: m.group(1).upper(),
    ),
    (
        IdKind.OPERATOR_APPROVAL,
        re.compile(r"\b(APPR-[A-Z0-9]{6,16})\b", re.IGNORECASE),
        lambda m: m.group(1).upper(),
    ),
    # Slug forms.
    (
        IdKind.DECISION,
        re.compile(
            r"\b((?:dec|decision)[_-][a-z0-9][a-z0-9_\-]{3,64}|decision_[a-z0-9][a-z0-9_\-]{3,64})\b",
            re.IGNORECASE,
        ),
        lambda m: m.group(1),
    ),
    (
        IdKind.PREFERENCE,
        re.compile(
            r"\b((?:pref|preference)[_-][a-z0-9][a-z0-9_\-]{3,64}|"
            r"preference_[a-z0-9][a-z0-9_\-]{3,64})\b",
            re.IGNORECASE,
        ),
        lambda m: m.group(1),
    ),
    (
        IdKind.OPEN_LOOP,
        re.compile(
            r"\b(LOOP-\d{8}-[A-F0-9]{6}|(?:ol|open[_-]?loop)[_-][a-z0-9][a-z0-9_\-]{3,64}|"
            r"open[_-]?loop_[a-z0-9][a-z0-9_\-]{3,64})\b",
            re.IGNORECASE,
        ),
        lambda m: m.group(1),
    ),
    (
        IdKind.OPERATOR_APPROVAL,
        re.compile(r"\b((?:appr|approval)[_-][a-z0-9][a-z0-9_\-]{6,64})\b", re.IGNORECASE),
        lambda m: m.group(1),
    ),
    (
        IdKind.PROMOTION_BUNDLE,
        re.compile(
            r"\b((?:promob|promotion[_-]?bundle)[_-][a-z0-9][a-z0-9_\-]{6,64})\b",
            re.IGNORECASE,
        ),
        lambda m: m.group(1),
    ),
    (
        IdKind.SESSION,
        re.compile(r"\b((?:sess|session)[_-][a-z0-9][a-z0-9_\-]{6,64})\b", re.IGNORECASE),
        lambda m: m.group(1),
    ),
    (
        IdKind.SOURCE,
        re.compile(r"\b((?:src|source)[_-][a-z0-9][a-z0-9_\-]{6,64})\b", re.IGNORECASE),
        lambda m: m.group(1),
    ),
]

_HEX_ID_ARGS = frozenset({
    "pack_id",
    "context_pack_id",
    "feedback_id",
    "quality_run_id",
    "stage_id",
    "receipt_id",
})
_HEX_ID_RE = re.compile(r"\b([a-f0-9]{24})\b", re.IGNORECASE)

# Map IdKind → arg names for reverse lookup.
_KIND_TO_ARGS: dict[IdKind, list[str]] = {}
for _arg, (_kind, _) in _ARG_BINDINGS.items():
    _KIND_TO_ARGS.setdefault(_kind, []).append(_arg)


def _unwrap_markdown_spans(prompt: str) -> str:
    """Replace backtick spans with inner text so IDs inside `...` are discoverable."""
    return re.sub(r"`([^`]+)`", r"\1", prompt)


def _validate_token(kind: IdKind, value: str) -> ValidationState:
    if len(value) > _TYPED_CANONICAL_MAX_LEN and kind in (
        IdKind.DECISION,
        IdKind.PREFERENCE,
        IdKind.OPEN_LOOP,
    ):
        return ValidationState.OVERLONG
    if kind == IdKind.DECISION and value.upper().startswith("DEC-"):
        if not re.fullmatch(r"DEC-\d{8}-[A-F0-9]{6}", value, re.IGNORECASE):
            return ValidationState.INVALID_SUFFIX
    if kind == IdKind.PREFERENCE and value.upper().startswith("PREF-"):
        if not re.fullmatch(r"PREF-\d{8}-[A-F0-9]{6}", value, re.IGNORECASE):
            return ValidationState.INVALID_SUFFIX
    if kind == IdKind.OPEN_LOOP and value.upper().startswith("LOOP-"):
        if not re.fullmatch(r"LOOP-\d{8}-[A-F0-9]{6}", value, re.IGNORECASE):
            return ValidationState.INVALID_SUFFIX
    if kind == IdKind.PROMOTION_BUNDLE and value.upper().startswith("PROMOB-"):
        if re.fullmatch(r"PROMOB-\d{8}", value, re.IGNORECASE):
            return ValidationState.PARTIAL_MATCH
    return ValidationState.VALID


def _clause_window(prompt: str, start: int, end: int) -> str:
    """Clause containing the ID span (semicolon/comma bounded, else full prompt)."""
    left_bound = max(prompt.rfind(";", 0, start), prompt.rfind(",", 0, start))
    right_semi = prompt.find(";", end)
    right_comma = prompt.find(",", end)
    right_candidates = [x for x in (right_semi, right_comma) if x != -1]
    right_bound = min(right_candidates) if right_candidates else len(prompt)
    return prompt[(left_bound + 1 if left_bound != -1 else 0) : right_bound]


def is_illustrative_mention(prompt: str, start: int, end: int) -> bool:
    """True when a typed ID is an example or quote-only mention, not a retrieval target."""
    before = prompt[max(0, start - 80):start]
    if re.search(r"\b(for example|e\.g\.|such as)\b", before, re.IGNORECASE):
        return True
    if re.search(r"\bmentions?\b", before, re.IGNORECASE):
        return True
    clause = _clause_window(prompt, start, end)
    if _RETRIEVAL_VERB_RE.search(clause):
        return False
    left = prompt.rfind('"', 0, start)
    right = prompt.find('"', end)
    if left != -1 and right != -1 and left < start and right >= end:
        return True
    left = prompt.rfind("'", 0, start)
    right = prompt.find("'", end)
    if left != -1 and right != -1 and left < start and right >= end:
        return True
    return False


def _resolve_span_overlaps(candidates: list[ParsedId]) -> list[ParsedId]:
    """Prefer longest valid span when patterns overlap (prevents PROMOB date truncation)."""
    if not candidates:
        return []
    ordered = sorted(
        candidates,
        key=lambda p: (-(p.source_span[1] - p.source_span[0]), p.source_span[0]),
    )
    kept: list[ParsedId] = []
    occupied: list[tuple[int, int]] = []
    for cand in ordered:
        s, e = cand.source_span
        if any(not (e <= os or s >= oe) for os, oe in occupied):
            continue
        kept.append(cand)
        occupied.append((s, e))
    return sorted(kept, key=lambda p: p.source_span[0])


def parse_prompt_ids(prompt: str) -> IdParseResult:
    """Extract all registered identifier types from a prompt."""
    surface = _unwrap_markdown_spans(prompt)
    raw: list[ParsedId] = []
    for kind, pattern, normalizer in _ID_PATTERNS:
        for match in pattern.finditer(surface):
            value = normalizer(match)
            state = _validate_token(kind, value)
            arg_names = _KIND_TO_ARGS.get(kind, [])
            arg_name = arg_names[0] if len(arg_names) == 1 else None
            tool = _ARG_BINDINGS.get(arg_name or "", (kind, None))[1] if arg_name else None
            raw.append(
                ParsedId(
                    id_type=kind,
                    value=value,
                    validation_state=state,
                    source_span=(match.start(), match.end()),
                    target_tool=tool,
                    arg_name=arg_name,
                )
            )
    ids = _resolve_span_overlaps(raw)
    by_arg: dict[str, list[ParsedId]] = {}
    for pid in ids:
        for arg in _KIND_TO_ARGS.get(pid.id_type, []):
            tagged = ParsedId(
                id_type=pid.id_type,
                value=pid.value,
                validation_state=pid.validation_state,
                source_span=pid.source_span,
                target_tool=_ARG_BINDINGS.get(arg, (pid.id_type, None))[1],
                arg_name=arg,
            )
            by_arg.setdefault(arg, []).append(tagged)
    conflicts = [
        pid.value
        for arg, group in by_arg.items()
        if len({p.value for p in group if p.validation_state == ValidationState.VALID}) > 1
        for pid in group
        if pid.validation_state == ValidationState.VALID
    ]
    return IdParseResult(ids=ids, by_arg=by_arg, conflicts=sorted(set(conflicts)))


def _extract_hex_id(prompt: str) -> str | None:
    """Return a sole 24-hex token when unambiguous (pack/feedback/stage/quality/receipt IDs)."""
    matches = [m.group(1).lower() for m in _HEX_ID_RE.finditer(prompt)]
    if len(matches) != 1:
        return None
    return matches[0]


def _is_illustrative_value(prompt: str, value: str) -> bool:
    surface = _unwrap_markdown_spans(prompt)
    for text in (surface, prompt):
        idx = text.find(value)
        if idx != -1:
            return is_illustrative_mention(text, idx, idx + len(value))
    return False


def extract_validated_id(prompt: str, arg_name: str) -> str | None:
    """Return exactly one validated ID for a tool argument, or None on ambiguity/absence."""
    if arg_name not in _ARG_BINDINGS:
        return None
    result = parse_prompt_ids(prompt)
    matches = result.by_arg.get(arg_name, [])
    valid = [m for m in matches if m.validation_state == ValidationState.VALID]
    if len(valid) == 1:
        if _is_illustrative_value(prompt, valid[0].value):
            return None
        return valid[0].value
    if arg_name in _HEX_ID_ARGS:
        hex_id = _extract_hex_id(_unwrap_markdown_spans(prompt))
        if hex_id and _is_illustrative_value(prompt, hex_id):
            return None
        return hex_id
    return None


def extract_asserted_typed_ids(prompt: str) -> list[tuple[str, str]]:
    """Return (prefix, canonical_id) pairs for DEC/PREF/LOOP retrieval targets."""
    result = parse_prompt_ids(prompt)
    prefix_map = {
        IdKind.DECISION: "DEC",
        IdKind.PREFERENCE: "PREF",
        IdKind.OPEN_LOOP: "LOOP",
        IdKind.OUTPUT: "OUTPUT",
        IdKind.PROMOTION_RECEIPT: "PROMO",
    }
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for pid in result.ids:
        if pid.id_type not in prefix_map:
            continue
        if pid.validation_state != ValidationState.VALID:
            continue
        if _is_illustrative_value(prompt, pid.value):
            continue
        token = pid.value.upper() if pid.value.upper().startswith(
            ("DEC-", "PREF-", "LOOP-", "OUTPUT-", "PROMO-")
        ) else pid.value
        if token in seen:
            continue
        seen.add(token)
        out.append((prefix_map[pid.id_type], token))
    return out


def validate_tool_argument_ids(tool_name: str, arguments: dict[str, Any]) -> dict[str, str]:
    """Validate ID-shaped argument values; returns field→error_code for invalid values."""
    errors: dict[str, str] = {}
    for field, value in arguments.items():
        if not field.endswith("_id") or value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        kind, _ = _ARG_BINDINGS.get(field, (None, None))
        if kind is None:
            continue
        state = _validate_token(kind, text)
        if state != ValidationState.VALID:
            errors[field] = f"invalid_{field}:{state.value}"
    return errors