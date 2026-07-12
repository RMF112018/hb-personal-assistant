"""Canonical file-root -> structure-root mapping authority (A3).

ONE shared resolver used by health, bootstrap, and watcher readiness so a file-index root_key resolves to
a structure-index root_key identically everywhere. Deterministic precedence:

    validated one-operation CLI override  (provenance ``cli_override``)
      -> configured explicit ``structure_root_map``  (provenance ``explicit_map``)
      -> exact NORMALIZED key match  (provenance ``exact_match``)
      -> unmapped

There is NO fuzzy substring / prefix / suffix / case / first-row fallback — the audit's health-only
`syn-` strip + bidirectional substring loop is removed. Invalid or ambiguous configuration fails closed
(``invalid_explicit_map`` / ``ambiguous_configuration``). The resolver deals only in neutral root keys and
never in absolute paths.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

# Mapping reason / provenance codes.
REASON_CLI_OVERRIDE = "cli_override"
REASON_EXPLICIT_MAP = "explicit_map"
REASON_EXACT_MATCH = "exact_match"
REASON_UNMAPPED = "unmapped"
REASON_INVALID_EXPLICIT_MAP = "invalid_explicit_map"
REASON_AMBIGUOUS = "ambiguous_configuration"
# The mapping authority (application configuration) could not be loaded or was invalid. This is a
# fail-CLOSED outcome distinct from ``unmapped``: with no trustworthy config the root's structure mapping is
# unknown, so a caller must NOT treat the root as structure-ready or fall back to identity matching.
REASON_CONFIG_UNAVAILABLE = "mapping_configuration_unavailable"


def normalize_root_key(key: str | None) -> str:
    """The ONE shared root-key normalizer (validation, lookup, serialization, readiness all use it).

    NFC-normalize and strip surrounding whitespace. Deliberately NO case folding — real keys are
    lowercase and distinct keys must never be collapsed by guessing. Duplicate detection is performed on
    the normalized form.
    """
    if not key:
        return ""
    return unicodedata.normalize("NFC", str(key)).strip()


@dataclass(frozen=True)
class StructureRootMapping:
    """Structured resolution result. ``structure_key`` is the RAW matching structure key (safe to look up
    in the structure repository); ``reason`` is both the outcome code and the provenance."""

    file_key: str
    structure_key: str | None
    reason: str

    @property
    def provenance(self) -> str:
        return self.reason

    @property
    def is_mapped(self) -> bool:
        return self.structure_key is not None


def _normalize_map(raw: Mapping[str, str] | None) -> tuple[dict[str, str], set[str]]:
    """Return (normalized source-key -> normalized target-key, ambiguous normalized source keys).

    A raw dict cannot have duplicate raw keys, but two raw keys can normalize to the SAME source key with
    conflicting targets (e.g. ``"work"`` and ``"work "``) — those are flagged ambiguous."""
    out: dict[str, str] = {}
    ambiguous: set[str] = set()
    for k, v in (raw or {}).items():
        nk = normalize_root_key(k)
        nv = normalize_root_key(v)
        if nk in out and out[nk] != nv:
            ambiguous.add(nk)
        out[nk] = nv
    return out, ambiguous


def _namespace(structure_keys: Iterable[str] | None) -> dict[str, str]:
    """Normalized structure key -> the first raw key that produced it (so callers get a lookup-safe key)."""
    ns: dict[str, str] = {}
    for k in structure_keys or []:
        ns.setdefault(normalize_root_key(k), k)
    return ns


def resolve_structure_mapping(
    file_key: str,
    structure_keys: Iterable[str] | None,
    *,
    config_map: Mapping[str, str] | None = None,
    cli_override: Mapping[str, str] | None = None,
) -> StructureRootMapping:
    """Resolve ``file_key`` to a structure root key against the ``structure_keys`` namespace.

    ``config_map`` is the durable configured explicit map; ``cli_override`` is a higher-precedence
    one-operation override. Never raises on degenerate input — an unmapped/invalid mapping fails closed."""
    nfk = normalize_root_key(file_key)
    ns = _namespace(structure_keys)
    if not nfk:
        return StructureRootMapping(nfk, None, REASON_UNMAPPED)

    for source_map, reason in (
        (cli_override, REASON_CLI_OVERRIDE),
        (config_map, REASON_EXPLICIT_MAP),
    ):
        if not source_map:
            continue
        norm, ambiguous = _normalize_map(source_map)
        if nfk in ambiguous:
            return StructureRootMapping(nfk, None, REASON_AMBIGUOUS)
        if nfk in norm:
            target = norm[nfk]
            if target in ns:
                return StructureRootMapping(nfk, ns[target], reason)
            return StructureRootMapping(nfk, None, REASON_INVALID_EXPLICIT_MAP)

    if nfk in ns:
        return StructureRootMapping(nfk, ns[nfk], REASON_EXACT_MATCH)
    return StructureRootMapping(nfk, None, REASON_UNMAPPED)


def validate_structure_root_map(
    config_map: Mapping[str, str] | None,
    structure_keys: Iterable[str] | None,
) -> list[dict[str, str]]:
    """Surface configuration errors for operators: duplicate normalized source keys with conflicting
    targets (``ambiguous_configuration``) and explicit targets that do not exist (``invalid_explicit_map``).
    Many-to-one (several source keys -> one structure key) is VALID and never reported."""
    errors: list[dict[str, str]] = []
    norm, ambiguous = _normalize_map(config_map)
    ns = _namespace(structure_keys)
    for src in sorted(ambiguous):
        errors.append(
            {
                "source_key": src,
                "reason": REASON_AMBIGUOUS,
                "detail": "duplicate source key after normalization with conflicting targets",
            }
        )
    for src, target in sorted(norm.items()):
        if src in ambiguous:
            continue
        if target not in ns:
            errors.append(
                {
                    "source_key": src,
                    "reason": REASON_INVALID_EXPLICIT_MAP,
                    "detail": "explicit target is not a configured structure root",
                }
            )
    return errors
