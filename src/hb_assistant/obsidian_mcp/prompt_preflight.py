"""Prompt Preflight — deterministic route engine (read-only, no content reads).

Given a raw prompt, classify intent → source-of-truth → candidate families → workflow recipe → specific
tools → authorization → retrieval budget → memory opportunity → fallback plan, and emit a single route plan
dict. This module performs NO writes, NO staging, NO promotion, and reads NO source content — it only reasons
over the static routing manifests (families / workflows / tool entries) plus optional live availability and
freshness signals. Organization-neutral.

Route schema version 2 is additive: existing top-level fields and deprecated
``prompt_authorizes_execution`` are preserved for the current contract cycle.
"""

from __future__ import annotations

import re
from typing import Any

from .canonical_tool_specs import KNOWN_TOOL_GROUPS
from .prompt_id_parser import (
    extract_asserted_typed_ids as _extract_asserted_typed_ids,
    extract_validated_id as _extract_validated_id,
    is_illustrative_mention as _is_non_target_id_mention,
)
from .tool_family_manifest import family_record
from .tool_metadata_types import ROUTE_SCHEMA_VERSION
from .workflow_recipe_manifest import WORKFLOWS, workflow_record

# Source-of-truth label per family (§10).
_SOURCE_OF_TRUTH: dict[str, str] = {
    "client_output_workspace": "generated outputs workspace (outputs root; NOT the vault)",
    "output_receipts_manifests": "generated outputs receipts/manifest",
    "artifact_workspace": "staged artifact proposals (not yet canonical)",
    "canonical_promotion": "canonical memory (Obsidian cards)",
    "obsidian_materialization": "canonical memory (Obsidian cards)",
    "assistant_decision_memory": "canonical decision/preference/open-loop records",
    "assistant_source_connector": "indexed source files",
    "assistant_navigation": "indexed source files + generated cards + vault notes",
    "assistant_context_packs": "durable context packs (source-backed)",
    "assistant_memory": "compiled memory (source-backed)",
    "assistant_research_packets": "research packets (citation-backed answer CONTEXT)",
    "assistant_answer_drafts": "citation-safe answer drafts (advisory)",
    "status_health": "server status (not content)",
    "tool_catalog_help_query": "tool catalog (not content)",
    "client_tool_manifest": "tool operating manifest",
    "prompt_routing": "routing manifests (advisory)",
}

_WRITE_CLASSES = frozenset({"staged_write", "canonical_promotion", "archive"})
_LAYER_ORDER = ("route_only", "metadata_discovery", "candidate_triage", "bounded_read", "deep_parse")

_MEMORY_CUES = (
    "remember that", "remember this", "for the future", "going forward", "from now on",
    "we decided", "i decided", "the decision is", "our preference", "i prefer", "always ",
    "never ", "make a note", "keep in mind", "standing rule",
)

_DESTRUCTIVE_VERBS = ("delete", "remove", "wipe", "destroy", "erase", "purge", "rm -")
_DESTRUCTIVE_OBJECTS = ("vault", "note", "file", "readme", "card", "record", "folder", "document",
                        "page", ".md", "artifact", "output")

# Capability → workflow policies / trigger keywords that must not score under prohibition.
_CAPABILITY_POLICIES: dict[str, frozenset[str]] = {
    "promote": frozenset({"canonical_promotion"}),
    "write": frozenset({"staged_write", "canonical_promotion", "archive"}),
    "stage": frozenset({"staged_write"}),
    "archive": frozenset({"archive"}),
    "execute": frozenset({"staged_write", "canonical_promotion", "archive"}),
    "execute_non_read": frozenset({"staged_write", "canonical_promotion", "archive"}),
    "index": frozenset(),  # handled via must_not / constraints
    "deploy": frozenset(),
    "external_action": frozenset(),
}

# Keywords that indicate a workflow exercises a capability (for scoring blocks).
_CAPABILITY_TRIGGER_TOKENS: dict[str, tuple[str, ...]] = {
    "promote": ("promote", "make canonical", "finalize the decision", "apply promotion", "canonical"),
    "write": ("write", "create the file", "save as", "generate a", "commit the", "export"),
    "stage": (
        "stage", "staging", "document this", "document the", "document", "capture this", "capture",
        "submit for review", "queue for review", "put this up for review", "for review",
        "create a proposal", "create proposal", "make a proposal",
    ),
    "archive": ("archive",),
    "execute": ("execute", "go ahead and", "send it", "run the"),
    "index": ("reindex", "rebuild index", "refresh index"),
    "deploy": ("deploy", "restart the nas"),
    "external_action": ("send it", "send email", "send the", "email this"),
}

# Negators that open a prohibition window (clause-scoped).
_NEGATOR_PATTERNS = (
    r"\bdo not\b", r"\bdon't\b", r"\bnever\b", r"\bwithout\b", r"\bnot a\b",
    r"\bno write\b", r"\bno staging\b", r"\bno stage\b", r"\bno promote\b",
    r"\bplan only\b", r"\bread-only\b", r"\bread only\b",
)
_CLAUSE_SPLIT = re.compile(
    r"(?<=[.!?])\s+|[;\n]|,\s+and\b|\s+—\s+|\s+-\s+|\s+but\s+|\s+however\s+|\s+yet\s+",
    re.IGNORECASE,
)
# Window after negator: tokens to scan for capability words (clause-local).
_PROHIBITION_WINDOW = 12

_MODALITY_CAPABILITY_INQUIRY = re.compile(
    r"\b(can you|could you|how do i|how to|what tool|which tool|is it possible|"
    r"does the system|are you able to)\b",
    re.IGNORECASE,
)
_MODALITY_HYPOTHETICAL = re.compile(
    r"\b(what if|what would happen|what happens if|suppose|imagine|would it|could we|if i promoted)\b",
    re.IGNORECASE,
)
_QUOTED_SPAN = re.compile(
    r'"([^"]*)"|\'([^\']*)\'|'
    r"[\u201c]([^\u201d]*)[\u201d]|"
    r"[\u2018]([^\u2019]*)[\u2019]",
)
_ANAPHORA_PHRASE = re.compile(
    r"\b(that action|this action|do so|do that|perform that action|perform that)\b",
    re.IGNORECASE,
)
_WRITE_CAPABILITY_WORD = re.compile(
    r"\b(promot\w*|stag\w*|writ\w*|archiv\w*|deploy\w*|commit\w*|mutat\w*|send\w*|email\w*)\b",
    re.IGNORECASE,
)

# Explicit allow-read phrases even when execute is banned.
_ALLOW_READ_PHRASES = (
    "you may use read-only", "read-only tools", "beyond read-only", "beyond read only",
    "read only analysis", "read-only analysis", "may use read-only", "read-only analysis",
)

_READ_INTENT_RE = re.compile(
    r"\b(show|list|display|inspect|review|retrieve|get|see|what are)\b",
    re.IGNORECASE,
)
_READ_OBJECT_RE = re.compile(
    r"\b(staged actions?|action stages?|staged items?|feedback|open loops?|decisions?|"
    r"preferences?|proposals?|outputs?|files?|notes?)\b",
    re.IGNORECASE,
)
_SCOPED_EXECUTE_BAN_RE = re.compile(
    r"\b(?:do not|don't)\s+execute\b(?:\s+(?:them|those|it|anything|that|the staged|any action))?",
    re.IGNORECASE,
)


def _normalize_unicode_quotes(text: str) -> str:
    return (
        (text or "")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )


def _norm(text: str) -> str:
    return " ".join(_normalize_unicode_quotes(text).lower().split())


def _is_destructive(prompt_l: str) -> bool:
    return (any(v in prompt_l for v in _DESTRUCTIVE_VERBS)
            and any(o in prompt_l for o in _DESTRUCTIVE_OBJECTS))


def _is_read_only_posture(prompt_l: str) -> bool:
    """True when the operator frames the request as read-only work (not plan-only identify)."""
    return bool(re.search(r"\bread[- ]only\b", prompt_l))


def _split_clauses(prompt_l: str) -> list[str]:
    return [p.strip() for p in _CLAUSE_SPLIT.split(prompt_l) if p.strip()]


def _strip_quoted_spans(text: str) -> str:
    return _QUOTED_SPAN.sub(" ", text)


def _is_prohibition_clause(clause: str) -> bool:
    """True when a clause is a scoped negation (exclude from workflow trigger scoring)."""
    c = clause.strip()
    if not c:
        return False
    if re.match(r"^(do not|don't|never|no)\b", c, re.IGNORECASE):
        return True
    if re.search(r"\b(do not|don't|never|not perform|do not perform)\b", c, re.IGNORECASE):
        if _ANAPHORA_PHRASE.search(c) or re.search(r"\bperform that action\b", c, re.IGNORECASE):
            return True
        if not re.match(
            r"^(search|find|list|show|retrieve|read|audit|explain|inspect|get|open)\b",
            c,
            re.IGNORECASE,
        ):
            return bool(_WRITE_CAPABILITY_WORD.search(c))
    return False


def _clause_capability_referents(clauses: list[str]) -> list[tuple[set[str], bool]]:
    """Per-clause capabilities: (caps, from_quoted). Imperative referents authorize anaphora; quoted do not."""
    referents: list[tuple[set[str], bool]] = []
    for clause in clauses:
        quoted_caps: set[str] = set()
        for match in _QUOTED_SPAN.finditer(clause):
            inner = next((g for g in match.groups() if g), "") or ""
            for cap in _CAPABILITY_TRIGGER_TOKENS:
                if _capability_token_in_text(cap, inner):
                    quoted_caps.add(cap)
        if quoted_caps:
            # Quoted payload is authoritative — ignore wrapper residue ("the document says …").
            referents.append((quoted_caps, True))
            continue
        imperative_caps: set[str] = set()
        stripped = _strip_quoted_spans(clause).strip()
        if stripped and _classify_clause_modality(clause) == "imperative":
            for cap in _CAPABILITY_TRIGGER_TOKENS:
                if _capability_token_in_text(cap, stripped):
                    imperative_caps.add(cap)
        referents.append((imperative_caps, False))
    return referents


def _apply_anaphora_prohibitions(prompt_l: str, prohibitions: set[str]) -> None:
    """Negated anaphora ('do not perform that action') inherits the nearest prior capability referent."""
    clauses = _split_clauses(prompt_l)
    referents = _clause_capability_referents(clauses)
    for i, clause in enumerate(clauses):
        prior: set[str] = set()
        for j in range(i):
            prior.update(referents[j][0])
        if not prior:
            continue
        if re.search(r"\b(do not|don't|never|not perform|without)\b", clause, re.IGNORECASE):
            if _ANAPHORA_PHRASE.search(clause) or re.search(
                r"\bperform that action\b", clause, re.IGNORECASE
            ):
                prohibitions.update(prior)


def _classify_clause_modality(clause: str) -> str:
    """Classify a clause for routing: imperative | advisory | hypothetical | quoted | capability_inquiry."""
    c = clause.strip()
    if not c:
        return "advisory"
    if re.fullmatch(r'\s*["\'].*["\']\s*', c):
        return "quoted"
    if not _strip_quoted_spans(c).strip():
        return "quoted"
    if _MODALITY_HYPOTHETICAL.search(c):
        return "hypothetical"
    if c.endswith("?"):
        if _MODALITY_CAPABILITY_INQUIRY.search(c):
            return "capability_inquiry"
        return "advisory"
    if _MODALITY_CAPABILITY_INQUIRY.search(c) and not re.search(
        r"\b(search|find|list|show|retrieve|read|audit|explain|identify)\b",
        c,
        re.IGNORECASE,
    ):
        return "capability_inquiry"
    if re.search(
        r"\b("
        r"do|don't|never|stage|promote|search|find|write|archive|deploy|execute|"
        r"generate|create|save|commit|go ahead|list|retrieve|read|conduct|map|document|capture|record|log|"
        r"make|bundle|remember|export|build|package|submit|queue|put|look"
        r")\b",
        c,
        re.IGNORECASE,
    ):
        return "imperative"
    return "advisory"


_SEARCH_VERB_NORMALIZERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\blook\s+through\b", re.IGNORECASE), "search through"),
    (re.compile(r"\blook\s+in\b", re.IGNORECASE), "search in"),
)
_VAULT_SEARCH_CONTEXT = re.compile(
    r"\bsearch\s+the\s+vault\b|\bvault\s+for\b|\bsearch\s+vault\b",
    re.IGNORECASE,
)

_DOCUMENT_FIND_INTENT = re.compile(
    r"\b(?:find|search|locate|retrieve)\b.*\b(?:documents|(?:original\s+)?pdf|contracts?|original|files?)\b|"
    r"\b(?:documents|(?:original\s+)?pdf|contracts?|original)\b.*\b(?:find|search|locate|stored\s+under)\b|"
    r"\bfind\s+the\s+original\b",
    re.IGNORECASE,
)
_SOURCE_FILE_OBJECT = re.compile(
    r"\b(?:documents|original\s+pdf(?:\s+contract)?|pdf\s+(?:contract|file|document)|contracts?|"
    r"original|source\s+files?|project\s+file|indexed)\b",
    re.IGNORECASE,
)
_VAULT_OBJECT = re.compile(
    r"\b(?:vault|obsidian|meeting\s+notes?)\b",
    re.IGNORECASE,
)
_STRUCTURE_OBJECT = re.compile(
    r"\b(?:source\s+map|source\s+roots?|folder\s+(?:map|structure|tree)|"
    r"map\s+the\s+(?:root|folder|project)|structure\s+under|configured\s+source\s+roots?)\b",
    re.IGNORECASE,
)
_RECEIPT_INSPECTION_VERBS = re.compile(
    r"\b(?:inspect|explain|retrieve|search|review|what\s+(?:is|does)|show|open|display|read|was\s+it)\b",
    re.IGNORECASE,
)
_MIXED_FILES_NOTES_INTENT = re.compile(
    r"\bfiles?\s+and\s+notes?\b|\bnotes?\s+and\s+files?\b",
    re.IGNORECASE,
)
_RELEVANT_FILES_INTENT = re.compile(
    r"\b(?:which|what)\s+files?\s+(?:are\s+)?relevant\b|\bfiles?\s+(?:are\s+)?relevant\b",
    re.IGNORECASE,
)
_NOTES_WITH_STRUCTURED_ID = re.compile(
    r"`[^`]+`.*\bnotes?\b|\bnotes?\b.*`[^`]+`",
    re.IGNORECASE,
)
_OBJECT_TYPE_WORKFLOW_BOOSTS: dict[str, tuple[re.Pattern[str], int]] = {
    "source_file_search": (_SOURCE_FILE_OBJECT, 3),
    "vault_note_search": (_VAULT_OBJECT, 3),
    "source_root_map": (_STRUCTURE_OBJECT, 3),
    "source_folder_map": (_STRUCTURE_OBJECT, 2),
    "source_project_map": (
        re.compile(r"\b(?:project\s+folder|where\s+is\s+(?:the\s+)?project)\b", re.IGNORECASE),
        2,
    ),
}


def _normalize_retrieval_verbs(prompt_l: str) -> str:
    """Map look-through / look-in phrasing to search-equivalent tokens for scoring."""
    text = prompt_l
    for pattern, replacement in _SEARCH_VERB_NORMALIZERS:
        text = pattern.sub(replacement, text)
    return text


def _is_mixed_private_retrieval_intent(prompt_l: str) -> bool:
    """True when the prompt explicitly requests both NAS/source files and vault notes (F-014)."""
    normalized = _normalize_retrieval_verbs(prompt_l)
    if _MIXED_FILES_NOTES_INTENT.search(normalized):
        return True
    if not re.search(r"\bnotes?\b", normalized):
        return False
    if not re.search(r"\bfiles?\b", normalized):
        return False
    return bool(re.search(r"\b(?:find|search|look for|related to)\b", normalized, re.IGNORECASE))


def _object_type_workflow_boost(prompt_l: str, workflow_id: str) -> int:
    """Boost workflows whose object-type cues match the prompt (F-007 / F-015)."""
    normalized = _normalize_retrieval_verbs(prompt_l)
    boost = 0
    if workflow_id == "mixed_private_retrieval" and _is_mixed_private_retrieval_intent(normalized):
        boost += 8
    spec = _OBJECT_TYPE_WORKFLOW_BOOSTS.get(workflow_id)
    if spec is not None:
        pattern, points = spec
        if pattern.search(normalized):
            boost += points
    if workflow_id == "source_file_search" and _DOCUMENT_FIND_INTENT.search(normalized):
        boost += 4
    if workflow_id == "source_file_search" and _RELEVANT_FILES_INTENT.search(normalized):
        boost += 6
    if workflow_id == "vault_note_search" and _NOTES_WITH_STRUCTURED_ID.search(normalized):
        boost += 6
    if workflow_id == "source_root_map" and _DOCUMENT_FIND_INTENT.search(normalized):
        return -10
    if _VAULT_SEARCH_CONTEXT.search(normalized):
        if workflow_id == "vault_note_search":
            boost += 4
        elif workflow_id == "source_file_search":
            boost -= 4
    return boost


def _dominant_operation_modality(prompt_l: str) -> str:
    """Highest-signal modality across clauses (imperative wins over advisory)."""
    order = ("imperative", "advisory", "capability_inquiry", "hypothetical", "quoted")
    seen: set[str] = set()
    for clause in _split_clauses(prompt_l):
        seen.add(_classify_clause_modality(clause))
    for mod in order:
        if mod in seen:
            return mod
    return "advisory"


def _scoring_text(prompt_l: str, *, write_policy: bool) -> str:
    """Text surface used for workflow trigger scoring (modality- and quote-aware)."""
    prompt_l = _normalize_retrieval_verbs(prompt_l)
    clauses = _split_clauses(prompt_l)
    blocked_modalities = frozenset({"hypothetical", "capability_inquiry"})
    if any(_classify_clause_modality(c) in blocked_modalities for c in clauses):
        # Whole prompt carries advisory/hypothetical/inquiry framing — never score writes from it.
        if write_policy:
            return ""
        blocked_modalities = frozenset({"hypothetical"})

    chunks: list[str] = []
    for clause in clauses:
        if _is_prohibition_clause(clause):
            continue
        mod = _classify_clause_modality(clause)
        if mod in ("quoted", "hypothetical"):
            continue
        if write_policy:
            if mod == "capability_inquiry":
                continue
            if mod != "imperative":
                continue
        elif mod == "capability_inquiry" and _WRITE_CAPABILITY_WORD.search(clause):
            continue
        chunk = _strip_quoted_spans(clause).strip()
        if chunk:
            chunks.append(chunk)
    if chunks:
        return " ".join(chunks)

    if write_policy:
        # Minimal capture/generation trigger phrases (e.g. "remember this") without imperative verbs.
        fallback: list[str] = []
        for clause in clauses:
            if _is_prohibition_clause(clause):
                continue
            mod = _classify_clause_modality(clause)
            if mod in ("quoted", "hypothetical", "capability_inquiry"):
                continue
            chunk = _strip_quoted_spans(clause).strip()
            if chunk:
                fallback.append(chunk)
        return " ".join(fallback)
    return ""


def _capability_token_in_text(cap: str, text: str) -> bool:
    for ct in _CAPABILITY_TRIGGER_TOKENS.get(cap, ()):
        if " " in ct:
            if ct in text:
                return True
        elif re.search(rf"\b{re.escape(ct)}", text, re.IGNORECASE):
            return True
    return False


def _has_imperative_capability_intent(prompt_l: str, capability: str) -> bool:
    """True when an imperative, non-quoted clause exercises a write/stage/promote capability."""
    cap_tokens = _CAPABILITY_TRIGGER_TOKENS.get(capability, ())
    if not cap_tokens:
        return False
    clauses = _split_clauses(prompt_l)
    referents = _clause_capability_referents(clauses)
    for i, clause in enumerate(clauses):
        if _classify_clause_modality(clause) != "imperative":
            continue
        if re.search(r"\b(do not|don't|never)\b", clause, re.IGNORECASE):
            continue
        surface = _strip_quoted_spans(clause)
        if any(
            (ct in surface if " " in ct else re.search(rf"\b{re.escape(ct)}", surface, re.IGNORECASE))
            for ct in cap_tokens
        ):
            return True
        if _ANAPHORA_PHRASE.search(clause):
            prior_imperative: set[str] = set()
            for j in range(i):
                caps, from_quoted = referents[j]
                if not from_quoted:
                    prior_imperative.update(caps)
            if capability in prior_imperative:
                return True
    return False


def _execute_ban_scoped_to_read_intent(prompt_l: str) -> bool:
    """True when a read/inspect clause coexists with a scoped execute prohibition."""
    clauses = _split_clauses(prompt_l)
    read_clause = False
    scoped_execute_ban = False
    for clause in clauses:
        c = clause.strip()
        if _READ_INTENT_RE.search(c) and _READ_OBJECT_RE.search(c):
            read_clause = True
        if _SCOPED_EXECUTE_BAN_RE.search(c):
            scoped_execute_ban = True
        elif re.search(r"\b(?:do not|don't)\s+execute\b", c) and read_clause:
            scoped_execute_ban = True
    return read_clause and scoped_execute_ban


def _prohibition_operation_scopes(
    prompt_l: str, prohibitions: set[str],
) -> tuple[list[str], list[str]]:
    """Derive explicit prohibited/allowed operation lists after scope parsing."""
    prohibited: list[str] = []
    allowed: list[str] = []
    if "write" in prohibitions:
        prohibited.append("write")
    if "stage" in prohibitions:
        prohibited.append("stage")
    if "promote" in prohibitions:
        prohibited.append("promote")
    if "external_action" in prohibitions:
        prohibited.append("external_action")
    if "execute" in prohibitions:
        prohibited.append("execute_request")
    elif "execute_non_read" in prohibitions:
        prohibited.append("execute_non_read")
        if _execute_ban_scoped_to_read_intent(prompt_l):
            prohibited.append("execute_staged_actions")
    if _execute_ban_scoped_to_read_intent(prompt_l) or "execute_non_read" in prohibitions:
        allowed.extend(["read", "inspect", "list"])
    if _is_read_only_posture(prompt_l) or _reads_explicitly_allowed(prompt_l):
        if "read" not in allowed:
            allowed.append("read")
    return prohibited, allowed


def _extract_prohibitions(prompt_l: str) -> set[str]:
    """Return capability names prohibited by scoped negation (not keyword-wide).

    Critical: ``read-only`` authorizes bounded *read* tool calls. It must never be converted
    into a generic ``execute`` prohibition. Only an explicit ``do not execute`` / ``plan only``
    (without a beyond-read-only exception) bans non-advisory tool execution.
    """
    prohibitions: set[str] = set()
    read_scoped_execute = _execute_ban_scoped_to_read_intent(prompt_l)

    # Explicit execute bans (not implied by "read-only").
    # Vocabulary:
    # - ``execute`` — no tool calls (plan-only / identify-only)
    # - ``execute_non_read`` — ban write/stage/promote/external/etc., allow bounded reads
    beyond_read_only = bool(re.search(r"\bbeyond read[- ]only\b", prompt_l))
    if re.search(r"\bplan only\b", prompt_l):
        prohibitions.add("execute")
    if re.search(r"\bdo not execute\b", prompt_l) or re.search(r"\bdon't execute\b", prompt_l):
        if beyond_read_only:
            prohibitions.add("execute_non_read")
            prohibitions.update({"write", "stage", "promote", "external_action"})
        elif read_scoped_execute:
            prohibitions.add("execute_non_read")
        else:
            prohibitions.add("execute")

    # Read-only posture: ban mutation classes when listed.
    # Never add ``execute`` here — bounded read execution is the requested operation.
    if _is_read_only_posture(prompt_l):
        for cap, patterns in (
            ("write", (r"\bwrite\b", r"\bmutat", r"\bno write\b")),
            ("stage", (r"\bstage\b", r"\bstaging\b")),
            ("promote", (r"\bpromote\b", r"\bpromotion\b")),
            ("index", (r"\bindex\b", r"\breindex\b", r"\brefresh\b")),
            ("deploy", (r"\bdeploy\b",)),
            ("archive", (r"\barchive\b",)),
            ("external_action", (r"\bsend\b", r"\bemail\b")),
        ):
            if any(re.search(p, prompt_l) for p in patterns):
                prohibitions.add(cap)
        if re.search(r"\bmutat", prompt_l):
            prohibitions.add("write")
        # "do not execute any action" under read-only identify: still ban mutation classes
        if re.search(r"\bdo not execute any action\b", prompt_l) or re.search(
            r"\b(do not|don't) execute\b", prompt_l
        ):
            prohibitions.update({"write", "stage", "promote", "external_action"})

    # Phrase-level bans (capability-specific; do not fold write→execute).
    for phrase, caps in (
        (r"\bno write\b", {"write"}),
        (r"\bno staging\b", {"stage"}),
        (r"\bno stage\b", {"stage"}),
        (r"\bdo not write\b", {"write"}),
        (r"\bdon't write\b", {"write"}),
        (r"\bwithout writing\b", {"write"}),
        (r"\bdo not stage\b", {"stage"}),
        (r"\bdo not promote\b", {"promote"}),
        (r"\bdon't promote\b", {"promote"}),
        (r"\bdo not apply\b", {"promote"}),
        (r"\bdon't apply\b", {"promote"}),
        (r"\bdo not modify\b", {"write"}),
        (r"\bdon't modify\b", {"write"}),
        (r"\bnever promote\b", {"promote"}),
        (r"\bdo not deploy\b", {"deploy"}),
        (r"\bdo not\b[^\n.]{0,40}\bindex\b", {"index"}),
        (r"\bdo not\b[^\n.]{0,40}\brefresh\b", {"index"}),
        (r"\bdo not\b[^\n.]{0,40}\bmutat", {"write"}),
    ):
        if re.search(phrase, prompt_l):
            prohibitions.update(caps)

    # Clause-scoped: negator + nearby capability token within a bounded window.
    clauses = _split_clauses(prompt_l)
    for clause in clauses:
        c = clause.strip()
        if not c:
            continue
        if re.search(r"\bnot a\b", c) and "receipt" in c:
            continue
        if re.search(r"\bwithout\b", c) and not any(
            tok in c for tok in ("write", "promot", "stag", "execut", "deploy", "index")
        ):
            continue
        # "read-only" is a posture marker, not a capability negator by itself.
        if re.fullmatch(r"read[- ]only[:.]?", c) or c.startswith("read-only") and "do not" not in c:
            if "do not" not in c and "don't" not in c and "never" not in c:
                continue

        tokens = c.split()
        for i, tok in enumerate(tokens):
            window_text = " ".join(tokens[i:i + 3])
            # Do NOT treat bare "read-only" / "read" as negators — that caused execute false positives.
            is_neg = bool(re.match(r"^(do|don't|never|without|not|no|plan)$", tok)) or any(
                re.search(p, window_text) for p in (
                    r"\bdo not\b", r"\bdon't\b", r"\bnever\b", r"\bwithout\b",
                    r"\bnot a\b", r"\bno write\b", r"\bno staging\b", r"\bplan only\b",
                )
            )
            if not is_neg:
                continue
            span = " ".join(tokens[i:i + _PROHIBITION_WINDOW])
            # "beyond read-only" exception: ban non-read classes only (never generic ``execute``).
            if "beyond read-only" in span or "beyond read only" in span:
                prohibitions.add("execute_non_read")
                prohibitions.update({"write", "stage", "promote", "external_action"})
                continue
            for cap in _CAPABILITY_TRIGGER_TOKENS:
                if _capability_token_in_text(cap, span):
                    if cap == "promote" and "receipt" in span and "not a" in span:
                        continue
                    if cap == "execute" and (beyond_read_only or read_scoped_execute):
                        prohibitions.add("execute_non_read")
                        prohibitions.discard("execute")
                        continue
                    prohibitions.add(cap)

    # Posture cleanup: read-only work must not carry a naked execute ban unless plan-only/identify.
    if beyond_read_only or read_scoped_execute or (
        _is_read_only_posture(prompt_l)
        and not re.search(r"\bplan only\b", prompt_l)
        and not re.search(r"\b(identify which tool|which tool should be used)\b", prompt_l)
    ):
        prohibitions.discard("execute")
        if beyond_read_only:
            prohibitions.add("execute_non_read")
            prohibitions.update({"write", "stage", "promote", "external_action"})
        elif read_scoped_execute:
            prohibitions.add("execute_non_read")

    _apply_anaphora_prohibitions(prompt_l, prohibitions)

    return prohibitions


def _score_workflow(prompt_l: str, wf: dict[str, Any], prohibitions: set[str] | None = None) -> int:
    """Score workflow; triggers nested under prohibited capabilities do not add points."""
    prohibitions = prohibitions if prohibitions is not None else set()
    policy = wf.get("operator_authorization_policy", "read")
    write_policy = policy in _WRITE_CLASSES
    score_surface = _scoring_text(prompt_l, write_policy=write_policy)
    if not score_surface:
        return 0
    # Entire workflow banned by policy prohibition.
    for cap in prohibitions:
        banned_policies = _CAPABILITY_POLICIES.get(cap, frozenset())
        if policy in banned_policies:
            return 0
        # Promote workflows also matched by promote triggers under prohibition.
        if cap == "promote" and policy == "canonical_promotion":
            return 0
        if cap == "external_action" and "external" in wf.get("workflow_id", ""):
            return 0

    score = 0
    for phrase in wf["trigger_phrases"]:
        p = phrase.lower()
        if not p or p not in score_surface:
            continue
        # If this phrase is itself a capability token under prohibition, skip.
        skip = False
        for cap in prohibitions:
            for ct in _CAPABILITY_TRIGGER_TOKENS.get(cap, ()):
                if ct in p or p in ct:
                    skip = True
                    break
            if skip:
                break
        if skip:
            continue
        score += 2 if " " in p else 1

    wf_id = wf["workflow_id"]
    if wf_id == "inspect_promotion_receipt":
        if score == 0:
            return 0
        if "promotion receipt" in score_surface:
            if not _RECEIPT_INSPECTION_VERBS.search(score_surface):
                return 0
            if re.search(r"\b(?:vault|obsidian)\b", score_surface):
                return 0

    score += _object_type_workflow_boost(prompt_l, wf_id)
    return max(0, score)


_INTENT_TIE_TIER: dict[str, int] = {
    "capture": 0, "documentation": 0, "staged_write": 1, "generation": 2, "canonical_promotion": 3,
}
_DEFAULT_INTENT_TIER = 5


def _intent_tier(wf: dict[str, Any]) -> int:
    return min((_INTENT_TIE_TIER.get(ic, _DEFAULT_INTENT_TIER) for ic in wf["intent_classes"]),
               default=_DEFAULT_INTENT_TIER)


def _rank_workflows(
    prompt_l: str, prohibitions: set[str] | None = None,
) -> list[tuple[int, dict[str, Any]]]:
    prohibitions = prohibitions if prohibitions is not None else set()
    scored = [(_score_workflow(prompt_l, wf, prohibitions), wf) for wf in WORKFLOWS]
    scored = [(s, wf) for s, wf in scored if s > 0]
    scored.sort(key=lambda t: (-t[0], _intent_tier(t[1]), t[1]["workflow_id"]))
    return scored


def _try_hypothetical_promotion_plan_route(
    prompt: str,
    prompt_l: str,
    *,
    prohibitions: set[str],
    has_exact_id: bool,
    available_tools: frozenset[str] | set[str] | None,
    freshness: dict[str, Any] | None,
    tool_groups: dict[str, str | None] | None,
    runtime_policy: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Route advisory/hypothetical promotion questions to the planning workflow."""
    if "promote" in prohibitions:
        return None
    if not _MODALITY_HYPOTHETICAL.search(prompt_l):
        return None
    if not re.search(r"\bpromot", prompt_l, re.IGNORECASE):
        return None
    plan_wf = workflow_record("plan_canonical_promotion")
    if not plan_wf:
        return None
    return _route_workflow_plan(
        prompt,
        prompt_l,
        best_wf=plan_wf,
        best_score=3,
        ranked=[(3, plan_wf)],
        prohibitions=prohibitions,
        has_exact_id=has_exact_id,
        available_tools=available_tools,
        freshness=freshness,
        tool_groups=tool_groups,
        runtime_policy=runtime_policy,
    )


def _prefer_hypothetical_promotion_plan(
    prompt_l: str,
    best_wf: dict[str, Any],
    *,
    prohibitions: set[str],
) -> dict[str, Any]:
    """Advisory/hypothetical promotion questions → plan workflow, not apply."""
    if best_wf.get("workflow_id") != "apply_canonical_promotion":
        return best_wf
    if "promote" in prohibitions:
        return best_wf
    modality = _dominant_operation_modality(prompt_l)
    if modality not in ("hypothetical", "advisory"):
        return best_wf
    if _has_imperative_capability_intent(prompt_l, "promote"):
        return best_wf
    plan_wf = workflow_record("plan_canonical_promotion")
    return plan_wf if plan_wf else best_wf


def _retrieval_budget(wf: dict[str, Any], has_exact_id: bool) -> dict[str, Any]:
    layer = wf["default_retrieval_layer"]
    if layer in ("metadata_discovery", "candidate_triage") and has_exact_id:
        recommended_next = "bounded_read"
    else:
        idx = _LAYER_ORDER.index(layer) if layer in _LAYER_ORDER else 0
        recommended_next = _LAYER_ORDER[min(idx + 1, len(_LAYER_ORDER) - 1)]
    return {
        "default_layer": layer,
        "recommended_next_layer": recommended_next,
        "max_candidates": wf["max_default_candidates"],
        "max_chars": wf["max_default_chars"],
        "deep_parse_requires_operator_selection": True,
        "why_not_deep_read_all": (
            "Deep-reading every candidate is unbounded and unsafe; triage metadata first, then read only "
            "the operator-selected item within the char budget."
        ),
    }


def _plan_only_or_no_execute(prompt_l: str, prohibitions: set[str]) -> bool:
    """True when the prompt forbids tool *calls* (identify-only / plan-only).

    Read-only audits are NOT plan-only: they authorize bounded read tool calls.
    """
    # Identify-which-tool + do not execute → advisory only (no tool calls).
    if re.search(r"\b(identify which tool|which tool should be used)\b", prompt_l):
        if re.search(r"\b(do not execute|don't execute|do not run|do not execute any action)\b", prompt_l):
            return True
    if re.search(r"\bplan only\b", prompt_l):
        return True
    if re.search(r"\bdo not execute any action\b", prompt_l):
        return True
    # Bare "do not execute" without read-only posture and without beyond-read-only allow.
    if re.search(r"\b(do not|don't) execute\b", prompt_l):
        if (
            _is_read_only_posture(prompt_l)
            or re.search(r"\bbeyond read[- ]only\b", prompt_l)
            or _execute_ban_scoped_to_read_intent(prompt_l)
        ):
            # Read-only analysis / beyond-read-only / scoped read+execute-ban still allows reads.
            return False
        return True
    return False


def _reads_explicitly_allowed(prompt_l: str) -> bool:
    if any(p in prompt_l for p in _ALLOW_READ_PHRASES):
        return True
    if re.search(r"\bbeyond read[- ]only\b", prompt_l):
        return True
    # A read-only posture (audit/analysis) authorizes bounded reads.
    if _is_read_only_posture(prompt_l) and not _plan_only_or_no_execute(prompt_l, set()):
        return True
    return False


# Schema-aligned required args for tools when live schema index is empty (offline tests).
_TOOL_REQUIRED_ARGS: dict[str, tuple[str, ...]] = {
    "assistant_source_file_search": ("query",),
    "assistant_search_sources": ("query",),
    "assistant_search_cards": ("query",),
    "assistant_source_query_plan": ("prompt",),
    "assistant_get_decision": ("decision_id",),
    "assistant_get_preference": ("preference_id",),
    "assistant_get_open_loop": ("open_loop_id",),
    "pa_session_capture_stage": ("source_client", "session_title", "capture_trigger", "session_summary"),
    "pa_artifact_proposal_stage": ("session_id", "candidate_artifacts"),
    "pa_artifact_promotion_apply": ("promotion_bundle_id", "operator_approval_id"),
    "pa_output_commit": ("output_id", "operator_approval_id"),
    "pa_output_stage": ("title", "file_type", "content_mode"),
    "pa_output_metadata": ("output_id",),
    "pa_output_archive_plan": ("output_id",),
    "pa_artifact_promotion_receipt_get": ("promotion_receipt_id",),
    "assistant_get_feedback": ("feedback_id",),
    "assistant_get_action_stage": ("stage_id",),
    "assistant_source_file_read": ("source_id",),
}

_WORKFLOW_OUTPUT_FORMAT: dict[str, tuple[str, str]] = {
    "generate_csv_output": ("csv", "csv_text"),
    "generate_json_output": ("json", "json_text"),
    "generate_html_output": ("html", "html_text"),
    "generate_markdown_output": ("md", "markdown_text"),
    "generate_pdf_output": ("pdf", "pdf_from_html_or_markdown"),
    "generate_pptx_output": ("pptx", "pptx_from_markdown_or_json"),
    "generate_docx_output": ("docx", "docx_from_markdown_or_text"),
    "generate_xlsx_output": ("xlsx", "xlsx_from_csv"),
    "generate_zip_package": ("zip", "zip_base64"),
}

_QUERY_ARG_NAMES = frozenset({"query", "search_term"})
_PROMPT_ARG_NAMES = frozenset({"prompt"})
_TEXT_ARG_NAMES = frozenset({"session_summary", "session_title", "capture_trigger", "objective"})
_ID_ARG_SUFFIX = "_id"
_GETTER_TOOLS = frozenset({
    "assistant_get_decision",
    "assistant_get_preference",
    "assistant_get_open_loop",
    "assistant_get_vault_note",
    "assistant_get_feedback",
    "assistant_get_action_stage",
    "assistant_source_file_read",
    "pa_output_metadata",
    "pa_artifact_promotion_receipt_get",
})
_TOPICAL_LIST_TOOLS = frozenset({
    "assistant_list_decisions",
    "assistant_list_preferences",
    "assistant_list_open_loops",
})

_TYPED_RETRIEVAL_ROUTE: dict[str, tuple[str, str, str]] = {
    "DEC": ("decision_id", "assistant_get_decision", "canonical_decision_retrieval"),
    "PREF": ("preference_id", "assistant_get_preference", "canonical_preference_retrieval"),
    "LOOP": ("open_loop_id", "assistant_get_open_loop", "canonical_open_loop_retrieval"),
    "OUTPUT": ("output_id", "pa_output_metadata", "inspect_generated_output_metadata"),
    "PROMO": ("promotion_receipt_id", "pa_artifact_promotion_receipt_get", "inspect_promotion_receipt"),
}
_RETRIEVAL_VERB_RE = re.compile(
    r"\b(show(?:\s+me)?(?:\s+the)?|retrieve|get|open|display|inspect|review|explain)\b",
    re.IGNORECASE,
)
_ARTIFACT_NOUN_CUES: tuple[tuple[str, str], ...] = (
    ("open loop", "LOOP"),
    ("preference", "PREF"),
    ("decision", "DEC"),
    ("generated output", "OUTPUT"),
    ("output file", "OUTPUT"),
    ("output", "OUTPUT"),
    ("promotion receipt", "PROMO"),
)


def required_args_for_tool(tool_name: str) -> list[str]:
    """Return required argument names (live schema when available; static fallback)."""
    try:
        from hb_assistant.nas_mcp.tool_registration import (  # noqa: PLC0415
            derive_tool_arg_meta,
            live_tool_schema_index,
        )

        meta = derive_tool_arg_meta(tool_name, live_tool_schema_index())
        req = meta.get("required_args") or []
        if req:
            return [str(x) for x in req]
    except Exception:  # noqa: BLE001
        pass
    return list(_TOOL_REQUIRED_ARGS.get(tool_name, ()))


def _extract_topic_query(prompt_l: str) -> str | None:
    """Best-effort topical fragment (e.g. 'about X' / 'relate to X'); not an ID."""
    patterns = (
        r"\b(?:relate(?:d)?\s+to|pertain(?:s)?\s+to)\s+([a-z0-9][\w\s\-]{0,64}?)(?:\?|\.|$)",
        r"\b(?:remain|stays?)\s+(?:about|regarding)\s+([a-z0-9][\w\s\-]{0,64}?)(?:\?|\.|$)",
        r"\b(?:about|for|regarding|on)\s+(?:the\s+)?([a-z0-9][\w\s\-]{0,64}?)(?:\?|\.|$)",
    )
    for pat in patterns:
        m = re.search(pat, prompt_l, re.IGNORECASE)
        if m:
            return m.group(1).strip().lower()
    return None


def _infer_typed_retrieval_prefix(prompt_l: str) -> str | None:
    for noun, prefix in _ARTIFACT_NOUN_CUES:
        if noun in prompt_l:
            return prefix
    return None


def _has_dominant_search_intent(prompt_l: str) -> bool:
    """True when file/vault search is the primary imperative (ID mentions must not override)."""
    for clause in _split_clauses(prompt_l):
        if _is_prohibition_clause(clause):
            continue
        if not re.search(r"\b(?:search|find|look\s+(?:in|through|for))\b", clause, re.IGNORECASE):
            continue
        if re.search(
            r"\b(?:work\s+files?|nas|vault|obsidian|indexed|original|project\s+files?|files?|notes?)\b",
            clause,
            re.IGNORECASE,
        ):
            return True
    return False


def _extract_quoted_fragment(prompt: str) -> str | None:
    m = re.search(r'"([^"]{1,200})"|\'([^\']{1,200})\'', prompt)
    if not m:
        return None
    return (m.group(1) or m.group(2) or "").strip()


def _extract_search_query(prompt: str, prompt_l: str) -> str | None:
    """Extract a bounded search/query string from natural-language retrieval prompts."""
    prompt_l = _normalize_retrieval_verbs(prompt_l)
    quoted = _extract_quoted_fragment(prompt)
    if quoted:
        return quoted[:200]

    patterns: list[tuple[str, str | None]] = [
        (r"\b(?:which|what)\s+files?\s+(?:are\s+)?relevant\b", "relevant files"),
        (r"\bfiles?\s+(?:are\s+)?relevant\b", "relevant files"),
        (r"\bsearch\s+the\s+vault\s+for\s+(.+?)(?:[.?!]|$)", None),
        (r"\bsearch\s+(?:my\s+)?work\s+files?(?:\s+for\s+(.+?))?(?:[.?!]|$)", "work files"),
        (r"\bsearch(?:\s+the)?\s+nas(?:\s+files?)?(?:\s+for\s+(.+?))?(?:[.?!]|$)", "nas files"),
        (r"\bsearch(?:\s+indexed)?(?:\s+\w+){0,4}\s+for\s+(.+?)(?:[.?!]|$)", None),
        (r"\bsearch\s+through\s+(?:the\s+)?(.+?)(?:[.?!]|$)", None),
        (r"\b(?:find|look for|search for)\s+(?:the\s+)?(.+?)(?:[.?!]|$)", None),
        (r"\bfind\s+(?:my\s+)?project\s+notes(?:\s+about\s+(.+?))?(?:[.?!]|$)", "project notes"),
        (r"\bsearch\s+(?:my\s+)?(.+?)(?:[.?!]|$)", None),
    ]
    for pat, default in patterns:
        m = re.search(pat, prompt_l, flags=re.I)
        if not m:
            continue
        q = ""
        if m.lastindex and m.lastindex >= 1:
            q = (m.group(1) or "").strip()
        if not q and default:
            q = default
        if q:
            return q[:200]
    topic = _extract_topic_query(prompt_l)
    if topic:
        return topic[:200]
    return None


def _extract_output_title(prompt: str, prompt_l: str) -> str | None:
    """Bounded title extraction for generated-output staging (never invents approval/output ids)."""
    quoted = _extract_quoted_fragment(prompt)
    if quoted and len(quoted) <= 120:
        return quoted
    patterns = (
        r"\b(?:titled|called|named)\s+(.+?)(?:\s+with\b|\s+containing\b|[.?!]|$)",
        r"\breport\s+titled\s+(.+?)(?:[.?!]|$)",
        r"\btitle\s*[:=]\s*(.+?)(?:[.?!]|$)",
    )
    for pat in patterns:
        m = re.search(pat, prompt, re.IGNORECASE)
        if m:
            title = m.group(1).strip(" '\"")
            if title:
                return title[:120]
    return None


def _extract_output_content_text(prompt: str, prompt_l: str) -> str | None:
    """Best-effort content snippet for output staging when the operator supplies inline body text."""
    patterns = (
        r"\bwith\s+(?:content|body|text)\s+(.+?)(?:[.?!]|$)",
        r"\bcontaining\s+(.+?)(?:[.?!]|$)",
        r"\bwith\s+columns?\s+(.+?)(?:[.?!]|$)",
    )
    for pat in patterns:
        m = re.search(pat, prompt_l, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:2000]
    return None


def _output_format_for_workflow(workflow_id: str | None) -> tuple[str, str] | None:
    if not workflow_id:
        return None
    return _WORKFLOW_OUTPUT_FORMAT.get(workflow_id)


def _extract_session_fields(prompt: str, prompt_l: str) -> dict[str, str]:
    """Bounded session-capture fields for document_session (never invents approval/session ids)."""
    out: dict[str, str] = {}
    summary = ""
    for cue in ("document this session", "capture this session", "document this as"):
        if cue in prompt_l:
            summary = prompt.split(cue, 1)[-1].strip(" :.-")
            break
    if not summary:
        summary = prompt.strip()
    if summary:
        out["session_summary"] = summary[:2000]
        title = summary.split("\n", 1)[0].strip()
        out["session_title"] = (title[:120] if title else "session capture")
    out.setdefault("source_client", "connected_client")
    out.setdefault("capture_trigger", "operator_request")
    return out


def _extract_tool_arguments(
    prompt: str,
    prompt_l: str,
    tool_name: str,
    *,
    workflow_id: str | None = None,
) -> dict[str, Any]:
    """Populate tool arguments from the prompt using schema arg names (never invents IDs)."""
    args: dict[str, Any] = {}
    for arg in required_args_for_tool(tool_name):
        if arg in _QUERY_ARG_NAMES or arg in _PROMPT_ARG_NAMES:
            if arg in _PROMPT_ARG_NAMES:
                val = _extract_search_query(prompt, prompt_l) or prompt.strip()
                if val:
                    args[arg] = val[:2000]
            else:
                val = _extract_search_query(prompt, prompt_l)
                if val:
                    args[arg] = val
        elif arg.endswith(_ID_ARG_SUFFIX):
            extracted = _extract_validated_id(prompt, arg)
            if extracted:
                args[arg] = extracted
        elif arg == "source_client":
            args[arg] = "connected_client"
        elif arg == "capture_trigger":
            args[arg] = "operator_request"
        elif arg in _TEXT_ARG_NAMES:
            if arg in ("session_summary", "session_title"):
                for k, v in _extract_session_fields(prompt, prompt_l).items():
                    if k == arg:
                        args[arg] = v
    if tool_name == "pa_output_stage":
        fmt = _output_format_for_workflow(workflow_id)
        if fmt:
            args.setdefault("file_type", fmt[0])
            args.setdefault("content_mode", fmt[1])
        title = _extract_output_title(prompt, prompt_l)
        if title:
            args.setdefault("title", title)
        content = _extract_output_content_text(prompt, prompt_l)
        if content:
            args.setdefault("content_text", content)
    if tool_name in _TOPICAL_LIST_TOOLS:
        topic = _extract_topic_query(prompt_l)
        if topic and "query" not in args:
            args["query"] = topic[:200]
    return args


def _missing_required_args(tool_name: str, arguments: dict[str, Any]) -> list[str]:
    return [
        a for a in required_args_for_tool(tool_name)
        if arguments.get(a) in (None, "", [], {})
    ]


def _resolve_next_tool_step(
    tools: list[str],
    prompt: str,
    prompt_l: str,
    *,
    workflow_id: str | None = None,
) -> tuple[str | None, dict[str, Any], str | None]:
    """Pick the executable next tool and extracted args (exact-ID getter overrides discovery-first list)."""
    if not tools:
        return None, {}, None

    output_id = _extract_validated_id(prompt, "output_id")

    # Exact-ID getter: skip list/discovery when a validated id is present.
    for tool in tools:
        if tool not in _GETTER_TOOLS:
            continue
        args = _extract_tool_arguments(prompt, prompt_l, tool, workflow_id=workflow_id)
        id_args = [a for a in required_args_for_tool(tool) if a.endswith(_ID_ARG_SUFFIX)]
        if id_args and all(args.get(a) for a in id_args) and not _missing_required_args(tool, args):
            return tool, args, "exact_id_getter"

    if output_id and "pa_output_metadata" in tools:
        args = _extract_tool_arguments(prompt, prompt_l, "pa_output_metadata", workflow_id=workflow_id)
        args.setdefault("output_id", output_id)
        if not _missing_required_args("pa_output_metadata", args):
            return "pa_output_metadata", args, "exact_id_getter"

    for tool in tools:
        args = _extract_tool_arguments(prompt, prompt_l, tool, workflow_id=workflow_id)
        if not _missing_required_args(tool, args):
            return tool, args, "extracted"

    tool = tools[0]
    return tool, _extract_tool_arguments(prompt, prompt_l, tool, workflow_id=workflow_id), None


def _argument_extraction_view(
    tool_name: str | None,
    arguments: dict[str, Any],
    *,
    source: str | None,
) -> dict[str, Any]:
    req = required_args_for_tool(tool_name) if tool_name else []
    populated = sorted(k for k in req if arguments.get(k) not in (None, "", [], {}))
    missing = [a for a in req if a not in populated]
    return {
        "populated": populated,
        "missing": missing,
        "source": source if populated else "none",
    }


def _tool_surface_signals(
    tool_name: str | None,
    *,
    available_tools: frozenset[str] | set[str] | None,
    runtime_policy: dict[str, Any] | None,
) -> dict[str, bool]:
    """Resolve surface exposure signals for one tool (live index when present)."""
    rp = dict(runtime_policy or {})
    index = rp.get("tool_surface_index") or {}
    if tool_name and tool_name in index:
        entry = index[tool_name]
        return {
            "surface_available": bool(entry.get("server_policy_available", True)),
            "profile_enabled": bool(entry.get("profile_enabled", True)),
            "directly_exposed": bool(entry.get("directly_exposed", False)),
            "gateway_allowlisted": bool(entry.get("gateway_allowlisted", False)),
        }

    surface_available = True
    profile_enabled = True
    directly_exposed = True
    gateway_allowlisted = True
    if rp.get("surface_available") is not None:
        surface_available = bool(rp["surface_available"])
    elif tool_name and available_tools is not None:
        surface_available = tool_name in available_tools
    if rp.get("profile_enabled") is not None:
        profile_enabled = bool(rp["profile_enabled"])
    elif tool_name and available_tools is not None:
        profile_enabled = tool_name in available_tools
    if rp.get("directly_exposed") is not None:
        directly_exposed = bool(rp["directly_exposed"])
    if rp.get("gateway_allowlisted") is not None:
        gateway_allowlisted = bool(rp["gateway_allowlisted"])
    elif tool_name:
        try:
            from hb_assistant.nas_mcp.broker import GATEWAY_ALLOWLIST  # noqa: PLC0415

            gateway_allowlisted = tool_name in GATEWAY_ALLOWLIST
            if rp.get("directly_exposed") is None:
                directly_exposed = not gateway_allowlisted
        except Exception:  # noqa: BLE001
            gateway_allowlisted = True
            directly_exposed = True

    return {
        "surface_available": surface_available,
        "profile_enabled": profile_enabled,
        "directly_exposed": directly_exposed,
        "gateway_allowlisted": gateway_allowlisted,
    }


def _resolve_recommended_call_mode(signals: dict[str, bool]) -> str | None:
    """Prefer direct MCP exposure; fall back to gateway proxy when that is the only path."""
    if signals.get("directly_exposed"):
        return "direct"
    if signals.get("gateway_allowlisted"):
        return "gateway"
    return None


def _runtime_policy_permission(
    next_tool: str | None,
    *,
    available_tools: frozenset[str] | set[str] | None,
    runtime_policy: dict[str, Any] | None,
    freshness: dict[str, Any] | None,
) -> dict[str, Any]:
    """Best-effort runtime gate signals (additive; defaults optimistic when unknown)."""
    rp = dict(runtime_policy or {})
    fresh = freshness or {}
    safe_mode = bool(rp.get("safe_mode")) or bool(fresh.get("safe_mode"))
    token_scope_allowed = rp.get("token_scope_allowed")
    if token_scope_allowed is None:
        token_scope_allowed = True

    signals = _tool_surface_signals(
        next_tool,
        available_tools=available_tools,
        runtime_policy=runtime_policy,
    )
    call_mode = rp.get("recommended_call_mode") or _resolve_recommended_call_mode(signals)

    return {
        "safe_mode": safe_mode,
        "token_scope_allowed": bool(token_scope_allowed),
        "profile_enabled": signals["profile_enabled"],
        "gateway_allowlisted": signals["gateway_allowlisted"],
        "directly_exposed": signals["directly_exposed"],
        "surface_available": signals["surface_available"],
        "recommended_call_mode": call_mode,
    }


_EXECUTION_BLOCKER_PRECEDENCE: tuple[str, ...] = (
    "plan_only",
    "operation_prohibited",
    "surface_unavailable",
    "profile_disabled",
    "not_directly_exposed",
    "gateway_denied",
    "token_scope_denied",
    "no_recommended_tool",
    "missing_arguments",
    "approval_required",
    "safe_mode_active",
    "surface_stale",
    "not_authorized",
)


def _approval_status(
    *,
    approval_satisfied: bool,
    tool_needs_approval: bool,
    additional_approval: bool,
    promote_requested: bool,
    is_write: bool,
) -> str:
    """Tri-state approval posture (F-018): not_required | required_unsatisfied | satisfied."""
    if approval_satisfied:
        return "satisfied"
    needs = tool_needs_approval or additional_approval or (promote_requested and is_write)
    if not needs:
        return "not_required"
    return "required_unsatisfied"


def _extended_prompt_permission(
    *,
    allow_read: bool,
    staging_ok: bool,
    write_ok: bool,
    promote_perm: bool,
    external_ok: bool,
    prohibitions: set[str],
) -> dict[str, bool]:
    """Prompt-scoped permission dimensions (F-011)."""
    return {
        "read": allow_read,
        "stage": staging_ok,
        "write": write_ok,
        "promote": promote_perm,
        "external_action": external_ok,
        "execute_non_read": (
            "execute_non_read" not in prohibitions and "execute" not in prohibitions
        ),
        "index": "index" not in prohibitions,
        "deploy": "deploy" not in prohibitions,
    }


def _extended_server_policy_permission(action_class: str) -> dict[str, bool]:
    """Server-policy permission dimensions parallel to prompt_permission (F-011)."""
    return {
        "read": True,
        "stage": action_class == "staged_write",
        "write": action_class in _WRITE_CLASSES,
        "promote": action_class == "canonical_promotion",
        "external_action": False,
        "execute_non_read": action_class in _WRITE_CLASSES or action_class == "archive",
        "index": True,
        "deploy": True,
    }


def _capability_gates(prohibitions: set[str], *, action_class: str) -> dict[str, Any]:
    """Prompt-scoped capability gates (index/deploy/archive/external) with blocked reasons."""
    gates: dict[str, Any] = {}
    for cap in ("index", "deploy", "archive", "external_action"):
        blocked = cap in prohibitions
        gates[cap] = {
            "allowed": not blocked,
            "blocked_reason": f"prompt_prohibits_{cap}" if blocked else None,
        }
    if action_class == "archive" and "archive" not in prohibitions:
        gates["archive"]["allowed"] = True
        gates["archive"]["blocked_reason"] = None
    return gates


def _evaluate_executability(
    *,
    plan_only: bool,
    prohibitions: set[str],
    allow_read: bool,
    next_tool: str | None,
    missing: list[str],
    tool_needs_approval: bool,
    approval_satisfied: bool,
    promote_requested: bool,
    staging_ok: bool,
    write_ok: bool,
    promote_perm: bool,
    is_write: bool,
    runtime_policy: dict[str, Any],
    freshness_stale: bool,
) -> tuple[bool, str | None, bool]:
    """Ordered gate precedence for ``currently_executable`` (does not execute).

    First matching blocker wins (see ``_EXECUTION_BLOCKER_PRECEDENCE``). Missing required
    arguments — including ``operator_approval_id`` — always yield ``missing_arguments`` before
    ``approval_required`` (F-012).
    """
    approval_required_flag = False

    if plan_only or ("execute" in prohibitions and not allow_read):
        return False, "plan_only" if plan_only else "operation_prohibited", False

    if not runtime_policy.get("surface_available", True):
        return False, "surface_unavailable", False
    if not runtime_policy.get("profile_enabled", True):
        return False, "profile_disabled", False

    call_mode = runtime_policy.get("recommended_call_mode")
    if call_mode == "direct":
        if not runtime_policy.get("directly_exposed", True):
            return False, "not_directly_exposed", False
    elif call_mode == "gateway":
        if not runtime_policy.get("gateway_allowlisted", True):
            return False, "gateway_denied", False
    elif next_tool is not None:
        return False, "surface_unavailable", False
    if not runtime_policy.get("token_scope_allowed", True):
        return False, "token_scope_denied", False

    if next_tool is None:
        return False, "no_recommended_tool", False

    if missing:
        if next_tool == "pa_artifact_proposal_stage":
            return False, "missing_arguments", False
        if (
            next_tool == "pa_artifact_proposal_plan_promotion"
            and missing == ["proposal_bundle_id"]
        ):
            return True, None, approval_required_flag
        approval_required_flag = tool_needs_approval
        return False, "missing_arguments", approval_required_flag

    if tool_needs_approval and not approval_satisfied:
        return False, "approval_required", True
    if promote_requested and not approval_satisfied:
        return False, "approval_required", True

    if is_write and runtime_policy.get("safe_mode"):
        return False, "safe_mode_active", False
    if is_write and freshness_stale:
        return False, "surface_stale", False

    if not allow_read and not staging_ok and not write_ok and not promote_perm:
        return False, "not_authorized", False

    return True, None, approval_required_flag or tool_needs_approval


def _authorization(
    wf: dict[str, Any],
    confident: bool,
    *,
    prompt_l: str,
    prohibitions: set[str],
    next_tool: str | None = None,
    next_arguments: dict[str, Any] | None = None,
    has_exact_id: bool = False,
    argument_extraction: dict[str, Any] | None = None,
    available_tools: frozenset[str] | set[str] | None = None,
    runtime_policy: dict[str, Any] | None = None,
    freshness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Multi-dimensional authorization + request-level executability (does not execute)."""
    action_class = wf["operator_authorization_policy"]
    is_write = action_class in _WRITE_CLASSES
    plan_only = _plan_only_or_no_execute(prompt_l, prohibitions)
    allow_read = not plan_only  # supporting reads for write workflows included

    non_read_banned = "execute_non_read" in prohibitions or "execute" in prohibitions
    staging_ok = (
        action_class == "staged_write"
        and "stage" not in prohibitions
        and "write" not in prohibitions
        and not non_read_banned
        and not plan_only
        and (
            _has_imperative_capability_intent(prompt_l, "stage")
            or _has_imperative_capability_intent(prompt_l, "write")
        )
    )
    write_ok = (
        action_class == "staged_write"
        and "write" not in prohibitions
        and not non_read_banned
        and not plan_only
        and confident
        and _has_imperative_capability_intent(prompt_l, "write")
    )
    # Prompt may request promotion without satisfying approval — permission is separate.
    promote_requested = (
        action_class == "canonical_promotion"
        and "promote" not in prohibitions
        and not plan_only
        and _has_imperative_capability_intent(prompt_l, "promote")
    )
    promote_perm = promote_requested  # prompt_permission.promote
    promotion_authorized = False  # not cleared for execution without validation+approval
    external_ok = False
    if "external_action" in prohibitions:
        external_ok = False

    additional_approval = bool(
        action_class in ("canonical_promotion", "archive")
        or bool(wf.get("additional_approval_points"))
        or (action_class == "staged_write" and next_tool and "commit" in (next_tool or ""))
    )
    # Stage tools do not require approval IDs; commit/promote do.
    tool_needs_approval = bool(
        next_tool and (
            next_tool in ("pa_artifact_promotion_apply", "pa_tool_manifest_refresh_promote", "pa_output_commit")
            or next_tool.endswith("_commit")
            or "promotion_apply" in next_tool
        )
    )
    approval_points = list(wf["additional_approval_points"])
    approval_satisfied = False  # preflight never holds server-minted approval

    next_arguments = dict(next_arguments or {})
    req_args = required_args_for_tool(next_tool) if next_tool else []
    missing = [a for a in req_args if next_arguments.get(a) in (None, "", [], {})]
    # has_exact_id alone never invents IDs — only reduces ambiguity when args already present.
    if has_exact_id and missing and not any(_extract_validated_id(prompt_l, a) for a in missing):
        pass  # still missing

    freshness_stale = bool(_freshness_view(freshness, is_write).get("stale"))
    runtime_perm = _runtime_policy_permission(
        next_tool,
        available_tools=available_tools,
        runtime_policy=runtime_policy,
        freshness=freshness,
    )
    capability_gates = _capability_gates(prohibitions, action_class=action_class)

    currently_executable, blocked_reason, approval_required_flag = _evaluate_executability(
        plan_only=plan_only,
        prohibitions=prohibitions,
        allow_read=allow_read,
        next_tool=next_tool,
        missing=missing,
        tool_needs_approval=tool_needs_approval,
        approval_satisfied=approval_satisfied,
        promote_requested=promote_requested,
        staging_ok=staging_ok,
        write_ok=write_ok,
        promote_perm=promote_perm,
        is_write=is_write,
        runtime_policy=runtime_perm,
        freshness_stale=freshness_stale,
    )

    prompt_authorizes_execution = bool(allow_read and not plan_only and not is_write)
    prompt_permission = _extended_prompt_permission(
        allow_read=allow_read,
        staging_ok=staging_ok,
        write_ok=write_ok,
        promote_perm=promote_perm,
        external_ok=external_ok,
        prohibitions=prohibitions,
    )
    server_policy_permission = _extended_server_policy_permission(action_class=action_class)
    approval_status = _approval_status(
        approval_satisfied=approval_satisfied,
        tool_needs_approval=tool_needs_approval,
        additional_approval=additional_approval,
        promote_requested=promote_requested,
        is_write=is_write,
    )

    return {
        "action_class": action_class,
        "write_risk": wf["write_risk"],
        "requested_operation_class": action_class if action_class != "read" else "read",
        "operation_requested": action_class,
        "prompt_permission": prompt_permission,
        "server_policy_permission": server_policy_permission,
        "approval_satisfied": approval_satisfied,
        "approval_status": approval_status,
        "execution_blocker_precedence": list(_EXECUTION_BLOCKER_PRECEDENCE),
        "approval_required": approval_required_flag or tool_needs_approval,
        "currently_executable": currently_executable,
        "execution_blocked_reason": blocked_reason,
        "missing_required_arguments": missing,
        "read_tool_calls_authorized": allow_read and not plan_only,
        "advisory_planning_authorized": True,
        "staging_authorized": staging_ok,
        "external_action_authorized": external_ok,
        "write_authorized": False,  # commit never authorized by prompt alone
        "promotion_authorized": promotion_authorized,
        "additional_approval_required": additional_approval or tool_needs_approval,
        "requires_explicit_operator_go": bool(is_write),
        "approval_points": approval_points,
        "prohibitions": sorted(prohibitions),
        "operation_modality": _dominant_operation_modality(prompt_l),
        "argument_extraction": argument_extraction or _argument_extraction_view(
            next_tool, next_arguments, source=None,
        ),
        "runtime_policy_permission": runtime_perm,
        "recommended_call_mode": runtime_perm.get("recommended_call_mode"),
        "capability_gates": capability_gates,
        "write_blocked_by_staleness": bool(freshness_stale and is_write),
        "prompt_authorizes_execution": prompt_authorizes_execution,
        "prompt_authorizes_execution_deprecated": True,
    }


def _memory_opportunity(prompt_l: str, primary_family: str) -> dict[str, Any]:
    hit = next((cue.strip() for cue in _MEMORY_CUES if cue in prompt_l), None)
    detected = hit is not None and primary_family not in ("artifact_workspace", "canonical_promotion")
    return {
        "detected": detected,
        "cue": hit,
        "suggested_workflow": "document_session" if detected else None,
        "note": (
            "The prompt states a durable fact/preference. Offer to capture it via the artifact workspace "
            "(document_session) — but only stage after explicit operator confirmation."
        ) if detected else "",
        "must_not_auto_stage": True,
    }


def _fallback_plan(wf: dict[str, Any], is_write: bool) -> dict[str, Any]:
    return {
        "rules": list(wf["fallback_rules"]),
        "unsafe_fallback_blocked": is_write,
        "failure_recovery": wf["failure_recovery"],
        "tool": "hb_assistant_tool_query",
        "arguments_template": {
            "tool_name": (wf["tool_sequence"][0] if wf.get("tool_sequence") else "pa_prompt_route"),
            "arguments": {},
        },
    }


def _tool_group(name: str, tool_groups: dict[str, str | None] | None = None) -> str | None:
    if tool_groups and name in tool_groups and tool_groups[name] is not None:
        return tool_groups[name]
    return KNOWN_TOOL_GROUPS.get(name)


def _enrich_tool_steps(
    tools: list[str],
    *,
    available_tools: frozenset[str] | set[str] | None,
    authorization: dict[str, Any],
    primary_family: str,
    tool_groups: dict[str, str | None] | None = None,
    next_tool: str | None = None,
    next_arguments: dict[str, Any] | None = None,
    topic_query: str | None = None,
    runtime_policy: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    from .tool_family_manifest import family_for_tool  # noqa: PLC0415

    steps: list[dict[str, Any]] = []
    for i, t in enumerate(tools):
        group = _tool_group(t, tool_groups)
        signals = _tool_surface_signals(
            t,
            available_tools=available_tools,
            runtime_policy=runtime_policy,
        )
        available = signals["surface_available"]
        call_mode = _resolve_recommended_call_mode(signals)
        fam = family_for_tool(t, group) or primary_family
        args: dict[str, Any] = {}
        if t == next_tool and next_arguments:
            args = dict(next_arguments)
        shared_query = (next_arguments or {}).get("query") or topic_query
        if shared_query and "query" in required_args_for_tool(t) and "query" not in args:
            args = dict(args)
            args["query"] = shared_query
        if topic_query and t in _TOPICAL_LIST_TOOLS and "query" not in args:
            args = dict(args)
            args["query"] = topic_query
        req = required_args_for_tool(t)
        missing = [a for a in req if args.get(a) in (None, "", [], {})]
        is_next = t == next_tool
        step_auth = bool(authorization.get("read_tool_calls_authorized"))
        if t.startswith("pa_artifact") or "stage" in t or "session_capture" in t:
            step_auth = bool(
                authorization.get("staging_authorized")
                or authorization.get("read_tool_calls_authorized")
            )
        if "promotion_apply" in t or t == "ai_outputs_card_upsert":
            step_auth = bool(authorization.get("prompt_permission", {}).get("promote"))
        # Executability only for the next_step tool with full preconditions.
        if is_next:
            cex = bool(authorization.get("currently_executable")) and available and step_auth
            blocked = None if cex else (
                authorization.get("execution_blocked_reason")
                or ("missing_arguments" if missing else "not_authorized")
            )
        else:
            # Subsequent getter/list steps are not currently executable until prior selection.
            cex = False
            blocked = "awaiting_prior_step" if not missing else "missing_arguments"
        step: dict[str, Any] = {
            "tool": t,
            "tool_group": group,
            "family": fam,
            "surface": group,
            "arguments": args,
            "call_mode": call_mode,
            "available": available,
            "installed": available,
            "profile_enabled": signals["profile_enabled"],
            "directly_exposed": signals["directly_exposed"],
            "gateway_allowlisted": signals["gateway_allowlisted"],
            "server_policy_available": available,
            "authorized": step_auth and available,
            "authorization_reason": (
                "authorized" if step_auth and available
                else (blocked or "not_authorized")
            ),
            "currently_executable": cex,
            "execution_blocked_reason": blocked,
            "missing_required_arguments": missing,
        }
        if topic_query and t in _TOPICAL_LIST_TOOLS:
            step["topic_query"] = topic_query
            step["topical_discovery_supported"] = True
            step["topic_guidance"] = (
                f"Bounded topical query '{topic_query}' wired to the list filter."
            )
        elif topic_query and t.startswith("assistant_list_"):
            step["topic_query"] = topic_query
            step["topical_discovery_supported"] = False
            step["topic_guidance"] = (
                f"List filters by type/status only; apply topic '{topic_query}' when selecting "
                f"from the bounded result set."
            )
        steps.append(step)
    return steps


def _freshness_view(freshness: dict[str, Any] | None, is_write: bool) -> dict[str, Any]:
    if not freshness:
        return {"checked": False, "stale": False, "staleness_state": "unknown",
                "warnings": [], "write_blocked_by_staleness": False}
    state = str(freshness.get("staleness_state") or "unknown")
    stale = bool(freshness.get("stale")) or state in ("check_failed",)
    write_blocked = is_write and (
        stale or state in ("indeterminate", "check_failed")
    )
    return {
        "checked": True,
        "stale": stale,
        "staleness_state": state,
        "warnings": list(freshness.get("warnings", [])),
        "write_blocked_by_staleness": write_blocked,
        "categories": freshness.get("categories") or {},
        "category_status": freshness.get("category_status") or {},
    }


def _typed_id_ambiguity_route(
    prompt: str,
    prompt_l: str,
    *,
    conflicting_ids: list[str],
    artifact_label: str,
    freshness: dict[str, Any] | None,
    prohibitions: set[str],
) -> dict[str, Any]:
    base = _unknown_route(prompt, prompt_l, freshness, prohibitions)
    base["intent"] = {
        "primary_class": "typed_id_ambiguity",
        "classes": ["typed_id_ambiguity", "retrieval"],
    }
    base["clarifying_question"] = (
        f"Multiple {artifact_label} IDs were mentioned ({', '.join(conflicting_ids)}). "
        f"Which one should I retrieve?"
    )
    base["routing_rationale"] = (
        f"Multiple conflicting typed {artifact_label} IDs detected; "
        "do not silently pick the first ID."
    )
    base["route_confidence"] = "medium"
    base["conflicting_ids"] = list(conflicting_ids)
    base["route"] = {
        "intent": "typed_id_ambiguity",
        "source_of_truth": "canonical decision/preference/open-loop records",
        "family": "assistant_decision_memory",
        "workflow": "context_preflight",
        "confidence": "medium",
    }
    return base


def _route_workflow_plan(
    prompt: str,
    prompt_l: str,
    *,
    best_wf: dict[str, Any],
    best_score: int,
    ranked: list[tuple[int, dict[str, Any]]],
    prohibitions: set[str],
    has_exact_id: bool = False,
    available_tools: frozenset[str] | set[str] | None = None,
    freshness: dict[str, Any] | None = None,
    tool_groups: dict[str, str | None] | None = None,
    runtime_policy: dict[str, Any] | None = None,
    forced_next_tool: str | None = None,
    forced_next_args: dict[str, Any] | None = None,
    forced_extraction_source: str | None = None,
    forced_confidence: str | None = None,
    forced_rationale: str | None = None,
) -> dict[str, Any]:
    """Build a route plan from a selected workflow (shared by trigger scoring and typed-ID pre-pass)."""
    candidate_families: list[str] = []
    alt_workflows: list[str] = []
    for s, wf in ranked:
        if s >= best_score - 1:
            if wf["family_id"] not in candidate_families:
                candidate_families.append(wf["family_id"])
            if wf["workflow_id"] != best_wf["workflow_id"]:
                alt_workflows.append(wf["workflow_id"])

    primary_family = best_wf["family_id"]
    runner_up = ranked[1][0] if len(ranked) > 1 else 0
    if forced_confidence:
        confidence = forced_confidence
    elif best_score >= 3 or (best_score >= 2 and best_score - runner_up >= 2):
        confidence = "high"
    elif best_score >= 2 or (best_score == 1 and len(candidate_families) == 1):
        confidence = "medium"
    else:
        confidence = "low"
    confident = confidence in ("high", "medium")

    seq = list(best_wf["tool_sequence"])
    if available_tools is not None:
        unavailable = [t for t in seq if t not in available_tools]
        recommended_tools = [t for t in seq if t in available_tools]
    else:
        unavailable = []
        recommended_tools = seq
    workflow_available = not unavailable

    topic = _extract_topic_query(prompt_l)
    if forced_next_tool is not None:
        next_tool = forced_next_tool
        next_args = dict(forced_next_args or {})
        extraction_source = forced_extraction_source
    else:
        next_tool, next_args, extraction_source = _resolve_next_tool_step(
            recommended_tools, prompt, prompt_l, workflow_id=best_wf["workflow_id"],
        )
    if topic and next_tool in _TOPICAL_LIST_TOOLS:
        next_args = dict(next_args)
        next_args.setdefault("query", topic)

    action_class = best_wf["operator_authorization_policy"]
    is_write = action_class in _WRITE_CLASSES
    arg_view = _argument_extraction_view(next_tool, next_args, source=extraction_source)
    merged_runtime_policy = dict(runtime_policy or {})
    if available_tools is not None:
        if next_tool:
            merged_runtime_policy["surface_available"] = next_tool in available_tools
        elif unavailable:
            merged_runtime_policy["surface_available"] = False
    authorization = _authorization(
        best_wf, confident,
        prompt_l=prompt_l, prohibitions=prohibitions,
        next_tool=next_tool, next_arguments=next_args, has_exact_id=has_exact_id,
        argument_extraction=arg_view,
        available_tools=available_tools,
        runtime_policy=merged_runtime_policy,
        freshness=freshness,
    )

    fam = family_record(primary_family) or {}

    tool_steps = _enrich_tool_steps(
        recommended_tools,
        available_tools=available_tools,
        authorization=authorization,
        primary_family=primary_family,
        tool_groups=tool_groups,
        next_tool=next_tool,
        next_arguments=next_args,
        topic_query=topic,
        runtime_policy=merged_runtime_policy,
    )

    next_step = next(
        (s for s in tool_steps if s.get("tool") == next_tool),
        tool_steps[0] if tool_steps else None,
    )
    additional_steps = [s for s in tool_steps if s is not next_step]

    constraints = [f"prohibited:{c}" for c in sorted(prohibitions)]
    if extraction_source == "exact_id_getter" and next_tool in _GETTER_TOOLS:
        constraints.append(
            f"exact_id_getter={next_tool}; discovery list step deferred because a validated id was extracted"
        )
    must_not = list(best_wf["must_not_use"]) + list(fam.get("family_level_negative_instructions", []))
    if prohibitions:
        must_not = must_not + [f"prompt prohibits: {', '.join(sorted(prohibitions))}"]
    if topic and next_tool in _TOPICAL_LIST_TOOLS:
        constraints.append(
            f"topic_query={topic}; bounded query wired to {next_tool}."
        )
    elif topic and next_tool and next_tool.startswith("assistant_list_"):
        constraints.append(
            f"topic_query={topic}; list tools filter by type/status only — "
            f"apply topic '{topic}' when selecting from the bounded list "
            f"(topical discovery arg not supported on {next_tool})."
        )

    prohibited_ops, allowed_ops = _prohibition_operation_scopes(prompt_l, prohibitions)

    plan: dict[str, Any] = {
        "route_schema_version": ROUTE_SCHEMA_VERSION,
        "prompt": prompt,
        "prohibited_operations": prohibited_ops,
        "allowed_operations": allowed_ops,
        "intent": {
            "primary_class": best_wf["intent_classes"][0] if best_wf["intent_classes"] else "unknown",
            "classes": list(best_wf["intent_classes"]),
        },
        "source_of_truth": best_wf.get("source_of_truth") or _SOURCE_OF_TRUTH.get(primary_family, "unclassified"),
        "candidate_families": candidate_families,
        "primary_family": primary_family,
        "recommended_workflow": best_wf["workflow_id"],
        "alternative_workflows": alt_workflows,
        "recommended_tools": recommended_tools,
        "workflow_available": workflow_available,
        "unavailable_tools": unavailable,
        "authorization": authorization,
        "retrieval_budget": _retrieval_budget(best_wf, has_exact_id or bool(forced_next_tool)),
        "provenance_required": list(best_wf["required_provenance"]),
        "memory_opportunity": _memory_opportunity(prompt_l, primary_family),
        "must_not_use": must_not,
        "fallback_plan": _fallback_plan(best_wf, is_write),
        "route_confidence": confidence,
        "routing_rationale": forced_rationale or (
            f"Matched workflow '{best_wf['workflow_id']}' (score {best_score}) in family '{primary_family}'; "
            f"source of truth = {_SOURCE_OF_TRUTH.get(primary_family, 'unclassified')}."
        ),
        "clarifying_question": None,
        "preflight_is_read_only": True,
        "constraints": constraints,
        "warnings": list(constraints),
        "next_step": next_step,
        "additional_steps": additional_steps,
        "recommended_call_mode": authorization.get("recommended_call_mode"),
        "route": {
            "intent": (best_wf["intent_classes"][0] if best_wf["intent_classes"] else "unknown"),
            "source_of_truth": best_wf.get("source_of_truth") or _SOURCE_OF_TRUTH.get(primary_family, "unclassified"),
            "family": primary_family,
            "workflow": best_wf["workflow_id"],
            "confidence": confidence,
        },
    }

    if not confident and is_write:
        plan["clarifying_question"] = (
            f"This looks like a '{action_class}' action but intent is ambiguous. Confirm the target "
            f"(e.g. generated file vs canonical memory) before I stage anything."
        )
        plan["recommended_tools"] = []
        plan["recommended_workflow"] = "context_preflight"
        plan["next_step"] = None
        plan["additional_steps"] = []

    if re.search(r"\b(go ahead and send|send it|email this)\b", prompt_l):
        plan["warnings"] = list(plan.get("warnings") or []) + [
            "No external-action tool is available; do not invent send/email execution.",
        ]
        plan["authorization"]["external_action_authorized"] = False
        plan["authorization"]["currently_executable"] = False

    plan["freshness"] = _freshness_view(freshness, is_write)
    return plan


def _try_typed_id_first_route(
    prompt: str,
    prompt_l: str,
    *,
    prohibitions: set[str],
    available_tools: frozenset[str] | set[str] | None = None,
    freshness: dict[str, Any] | None = None,
    tool_groups: dict[str, str | None] | None = None,
    runtime_policy: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Route typed canonical IDs to direct getters before trigger-phrase scoring."""
    if _has_dominant_search_intent(prompt_l):
        return None
    if not _RETRIEVAL_VERB_RE.search(prompt_l):
        return None

    asserted = _extract_asserted_typed_ids(prompt)
    if not asserted:
        return None

    noun_prefix = _infer_typed_retrieval_prefix(prompt_l)
    if noun_prefix:
        asserted = [(pfx, tok) for pfx, tok in asserted if pfx == noun_prefix]
        if not asserted:
            return None

    by_prefix: dict[str, list[str]] = {}
    for pfx, tok in asserted:
        by_prefix.setdefault(pfx, []).append(tok)

    if len(by_prefix) > 1:
        return None

    prefix, tokens = next(iter(by_prefix.items()))
    route = _TYPED_RETRIEVAL_ROUTE.get(prefix)
    if not route:
        return None

    arg_name, getter_tool, workflow_id = route
    if prefix == "OUTPUT" and re.search(r"\breceipt\b", prompt_l):
        workflow_id = "retrieve_generated_output_receipt"
    artifact_label = next((n for n, p in _ARTIFACT_NOUN_CUES if p == prefix), prefix.lower())

    if len(tokens) > 1:
        return _typed_id_ambiguity_route(
            prompt, prompt_l,
            conflicting_ids=tokens,
            artifact_label=artifact_label,
            freshness=freshness,
            prohibitions=prohibitions,
        )

    best_wf = workflow_record(workflow_id)
    if not best_wf:
        return None

    token = tokens[0]
    return _route_workflow_plan(
        prompt, prompt_l,
        best_wf=best_wf,
        best_score=10,
        ranked=[(10, best_wf)],
        prohibitions=prohibitions,
        has_exact_id=True,
        available_tools=available_tools,
        freshness=freshness,
        tool_groups=tool_groups,
        runtime_policy=runtime_policy,
        forced_next_tool=getter_tool,
        forced_next_args={arg_name: token},
        forced_extraction_source="exact_id_getter",
        forced_confidence="high",
        forced_rationale=(
            f"Typed canonical ID '{token}' with retrieval verb → direct getter '{getter_tool}' "
            f"(workflow '{workflow_id}')."
        ),
    )


def route_prompt(
    prompt: str,
    *,
    available_tools: frozenset[str] | set[str] | None = None,
    has_exact_id: bool = False,
    freshness: dict[str, Any] | None = None,
    tool_groups: dict[str, str | None] | None = None,
    runtime_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a read-only route plan for ``prompt`` (schema v2, additive). Never writes or reads content."""
    prompt_l = _norm(prompt)
    prohibitions = _extract_prohibitions(prompt_l)

    if _is_destructive(prompt_l):
        return _destructive_route(prompt, prompt_l, freshness, prohibitions)

    if any(c in prompt_l for c in ("show me secrets", "show tokens", "dump credentials", "api keys",
                                   "extract password")):
        return _safety_refusal_route(
            prompt, prompt_l, freshness, prohibitions,
            intent="secret_extraction_refusal",
            rationale="Refuse secret/token extraction.",
        )
    if any(c in prompt_l for c in ("write a file to /tmp", "write to /tmp", "/tmp/anything",
                                   "save to /etc/")):
        return _safety_refusal_route(
            prompt, prompt_l, freshness, prohibitions,
            intent="arbitrary_path_write_refusal",
            rationale="Refuse arbitrary host path writes; use generated-output workspace only.",
        )

    # Negated noun assertions ("this is not a promotion receipt") are not retrieval intents.
    if _is_negated_noun_assertion(prompt_l):
        return _negated_assertion_route(prompt, prompt_l, freshness, prohibitions)

    # Ambiguous bare "notes" without vault/source/project cue → clarify once.
    if _is_ambiguous_notes(prompt_l):
        return _ambiguous_notes_route(prompt, prompt_l, freshness, prohibitions)

    typed_plan = _try_typed_id_first_route(
        prompt, prompt_l,
        prohibitions=prohibitions,
        available_tools=available_tools,
        freshness=freshness,
        tool_groups=tool_groups,
        runtime_policy=runtime_policy,
    )
    if typed_plan is not None:
        return typed_plan

    ranked = _rank_workflows(prompt_l, prohibitions)

    if not ranked:
        hypo_plan = _try_hypothetical_promotion_plan_route(
            prompt,
            prompt_l,
            prohibitions=prohibitions,
            has_exact_id=has_exact_id,
            available_tools=available_tools,
            freshness=freshness,
            tool_groups=tool_groups,
            runtime_policy=runtime_policy,
        )
        if hypo_plan is not None:
            return hypo_plan
        return _unknown_route(prompt, prompt_l, freshness, prohibitions)

    best_score, best_wf = ranked[0]
    best_wf = _prefer_hypothetical_promotion_plan(prompt_l, best_wf, prohibitions=prohibitions)
    if best_wf["workflow_id"] != ranked[0][1]["workflow_id"]:
        best_score = max(best_score, 2)
    return _route_workflow_plan(
        prompt, prompt_l,
        best_wf=best_wf,
        best_score=best_score,
        ranked=ranked,
        prohibitions=prohibitions,
        has_exact_id=has_exact_id,
        available_tools=available_tools,
        freshness=freshness,
        tool_groups=tool_groups,
        runtime_policy=runtime_policy,
    )


def _is_negated_noun_assertion(prompt_l: str) -> bool:
    """True for sentences that deny a noun label rather than request work.

    Example: "this is not a promotion receipt" — not a request to inspect receipts.
    """
    if re.search(r"\b(this is not a|that is not a|it's not a|it is not a|not a)\b", prompt_l):
        # Assertion about identity/classification, not an imperative request verb.
        if not re.search(
            r"\b(find|search|get|list|show|open|retrieve|inspect|read|stage|promote|create|write)\b",
            prompt_l,
        ):
            return True
        # Even with a verb, "this is not a X" is typically classification.
        if re.search(r"\bthis is not a\b", prompt_l) or re.search(r"\bthat is not a\b", prompt_l):
            return True
    return False


def _negated_assertion_route(
    prompt: str, prompt_l: str, freshness: dict[str, Any] | None, prohibitions: set[str],
) -> dict[str, Any]:
    base = _unknown_route(prompt, prompt_l, freshness, prohibitions)
    base["intent"] = {"primary_class": "negated_assertion", "classes": ["negated_assertion", "clarification"]}
    base["routing_rationale"] = (
        "Negated noun assertion detected (e.g. 'this is not a …'); not a tool/retrieval request."
    )
    base["clarifying_question"] = (
        "Understood as a classification statement, not a tool request. "
        "What would you like to do instead (retrieve, stage, review, or something else)?"
    )
    base["recommended_workflow"] = "context_preflight"
    base["recommended_tools"] = []
    base["next_step"] = None
    base["additional_steps"] = []
    base["route_confidence"] = "high"
    base["route"] = {
        "intent": "negated_assertion", "source_of_truth": "unclassified",
        "family": "prompt_routing", "workflow": "context_preflight", "confidence": "high",
    }
    return base


def _is_ambiguous_notes(prompt_l: str) -> bool:
    """Bare 'notes' without vault/source/project cue → one clarification."""
    if _is_mixed_private_retrieval_intent(prompt_l):
        return False
    if _NOTES_WITH_STRUCTURED_ID.search(prompt_l):
        return False
    if "notes" not in prompt_l:
        return False
    if any(k in prompt_l for k in (
        "vault", "obsidian", "meeting notes", "source", "nas", "work files",
        "project notes", "project file", "indexed",
    )):
        return False
    # Exactly vague patterns like "find my notes" / "handle notes"
    return bool(re.search(r"\b(find|search|get|show)\b.*\bnotes\b", prompt_l)) and "project" not in prompt_l


def _ambiguous_notes_route(
    prompt: str, prompt_l: str, freshness: dict[str, Any] | None, prohibitions: set[str],
) -> dict[str, Any]:
    base = _unknown_route(prompt, prompt_l, freshness, prohibitions)
    base["intent"] = {"primary_class": "ambiguous_notes", "classes": ["ambiguous_notes", "retrieval"]}
    base["clarifying_question"] = (
        "Do you mean Obsidian vault notes, indexed NAS project files, or generated cards?"
    )
    base["routing_rationale"] = "Ambiguous 'notes' without vault/source cue; ask one clarification."
    base["route_confidence"] = "low"
    return base


def _base_auth_read_only(
    prohibitions: set[str], *, allow_read: bool = False, prompt_l: str = "",
) -> dict[str, Any]:
    # Clarify routes recommend no tools — not currently executable even if reads are permitted.
    blocked = None if allow_read else "not_authorized"
    if allow_read:
        blocked = "no_recommended_tool"  # clarification / empty tool sequence
    prompt_permission = _extended_prompt_permission(
        allow_read=allow_read,
        staging_ok=False,
        write_ok=False,
        promote_perm=False,
        external_ok=False,
        prohibitions=prohibitions,
    )
    return {
        "action_class": "read",
        "write_risk": "none",
        "requested_operation_class": "read",
        "operation_requested": "read",
        "prompt_permission": prompt_permission,
        "server_policy_permission": _extended_server_policy_permission(action_class="read"),
        "approval_satisfied": False,
        "approval_status": "not_required",
        "execution_blocker_precedence": list(_EXECUTION_BLOCKER_PRECEDENCE),
        "currently_executable": False,
        "execution_blocked_reason": blocked if not allow_read else "no_recommended_tool",
        "read_tool_calls_authorized": allow_read,
        "advisory_planning_authorized": True,
        "staging_authorized": False,
        "external_action_authorized": False,
        "write_authorized": False,
        "promotion_authorized": False,
        "additional_approval_required": False,
        "requires_explicit_operator_go": False,
        "approval_points": [],
        "prohibitions": sorted(prohibitions),
        "operation_modality": _dominant_operation_modality(prompt_l) if prompt_l else "advisory",
        "argument_extraction": {"populated": [], "missing": [], "source": "none"},
        "runtime_policy_permission": _runtime_policy_permission(
            None, available_tools=None, runtime_policy=None, freshness=None,
        ),
        "capability_gates": _capability_gates(prohibitions, action_class="read"),
        "write_blocked_by_staleness": False,
        "missing_required_arguments": [],
        "prompt_authorizes_execution": allow_read,
        "prompt_authorizes_execution_deprecated": True,
    }


def _unknown_route(
    prompt: str, prompt_l: str, freshness: dict[str, Any] | None, prohibitions: set[str] | None = None,
) -> dict[str, Any]:
    prohibitions = prohibitions if prohibitions is not None else _extract_prohibitions(prompt_l)
    allow_read = _reads_explicitly_allowed(prompt_l) and not _plan_only_or_no_execute(prompt_l, prohibitions)
    if _reads_explicitly_allowed(prompt_l):
        allow_read = True
    return {
        "route_schema_version": ROUTE_SCHEMA_VERSION,
        "prompt": prompt,
        "intent": {"primary_class": "unknown", "classes": ["unknown"]},
        "source_of_truth": "unclassified",
        "candidate_families": ["prompt_routing"],
        "primary_family": "prompt_routing",
        "recommended_workflow": "context_preflight",
        "alternative_workflows": [],
        "recommended_tools": [],
        "workflow_available": True,
        "unavailable_tools": [],
        "authorization": _base_auth_read_only(prohibitions, allow_read=allow_read, prompt_l=prompt_l),
        "retrieval_budget": {
            "default_layer": "route_only", "recommended_next_layer": "metadata_discovery",
            "max_candidates": 10, "max_chars": 4000, "deep_parse_requires_operator_selection": True,
            "why_not_deep_read_all": "Intent is unclear; clarify before spending retrieval budget.",
        },
        "provenance_required": [],
        "memory_opportunity": _memory_opportunity(prompt_l, "prompt_routing"),
        "must_not_use": ["guessing a write/promotion target"],
        "fallback_plan": {"rules": [], "unsafe_fallback_blocked": True, "failure_recovery": ""},
        "route_confidence": "low",
        "routing_rationale": "No workflow trigger matched; route to a clarifying preflight.",
        "clarifying_question": "I couldn't confidently classify this request. What outcome do you want "
                               "(retrieve, generate a file, capture to memory, or promote)?",
        "preflight_is_read_only": True,
        "constraints": [f"prohibited:{c}" for c in sorted(prohibitions)],
        "warnings": [],
        "next_step": None,
        "additional_steps": [],
        "route": {
            "intent": "unknown", "source_of_truth": "unclassified", "family": "prompt_routing",
            "workflow": "context_preflight", "confidence": "low",
        },
        "freshness": _freshness_view(freshness, is_write=False),
    }


def _safety_refusal_route(
    prompt: str, prompt_l: str, freshness: dict[str, Any] | None, prohibitions: set[str],
    *, intent: str, rationale: str,
) -> dict[str, Any]:
    auth = _base_auth_read_only(prohibitions, allow_read=False, prompt_l=prompt_l)
    auth["additional_approval_required"] = True
    auth["requires_explicit_operator_go"] = True
    auth["approval_points"] = ["refusal — do not execute"]
    return {
        "route_schema_version": ROUTE_SCHEMA_VERSION,
        "prompt": prompt,
        "intent": {"primary_class": intent, "classes": [intent, "refusal"]},
        "source_of_truth": "unclassified",
        "candidate_families": ["prompt_routing"],
        "primary_family": "prompt_routing",
        "recommended_workflow": "context_preflight",
        "alternative_workflows": [],
        "recommended_tools": [],
        "workflow_available": True,
        "unavailable_tools": [],
        "authorization": auth,
        "retrieval_budget": {
            "default_layer": "route_only", "recommended_next_layer": "route_only",
            "max_candidates": 0, "max_chars": 0, "deep_parse_requires_operator_selection": True,
            "why_not_deep_read_all": rationale,
        },
        "provenance_required": [],
        "memory_opportunity": _memory_opportunity(prompt_l, "prompt_routing"),
        "must_not_use": [rationale, "any write or extract tool for this intent"],
        "fallback_plan": {"rules": ["refuse"], "unsafe_fallback_blocked": True, "failure_recovery": ""},
        "route_confidence": "high",
        "routing_rationale": rationale,
        "clarifying_question": rationale,
        "preflight_is_read_only": True,
        "constraints": [f"prohibited:{c}" for c in sorted(prohibitions)],
        "warnings": [],
        "next_step": None,
        "additional_steps": [],
        "route": {
            "intent": intent, "source_of_truth": "unclassified", "family": "prompt_routing",
            "workflow": "context_preflight", "confidence": "high",
        },
        "freshness": _freshness_view(freshness, is_write=False),
        "refused": True,
    }


def _destructive_route(
    prompt: str, prompt_l: str, freshness: dict[str, Any] | None, prohibitions: set[str],
) -> dict[str, Any]:
    auth = _base_auth_read_only(prohibitions | {"write", "execute"}, allow_read=False, prompt_l=prompt_l)
    auth["action_class"] = "destructive"
    auth["write_risk"] = "high"
    auth["requested_operation_class"] = "destructive"
    auth["additional_approval_required"] = True
    auth["requires_explicit_operator_go"] = True
    auth["approval_points"] = ["explicit operator confirmation of the exact target + irreversibility"]
    return {
        "route_schema_version": ROUTE_SCHEMA_VERSION,
        "prompt": prompt,
        "intent": {"primary_class": "destructive", "classes": ["destructive"]},
        "source_of_truth": "unclassified",
        "candidate_families": ["prompt_routing"],
        "primary_family": "prompt_routing",
        "recommended_workflow": "context_preflight",
        "alternative_workflows": [],
        "recommended_tools": [],
        "workflow_available": True,
        "unavailable_tools": [],
        "authorization": auth,
        "retrieval_budget": {
            "default_layer": "route_only", "recommended_next_layer": "route_only",
            "max_candidates": 0, "max_chars": 0, "deep_parse_requires_operator_selection": True,
            "why_not_deep_read_all": "Destructive intent — do not spend retrieval budget; confirm first.",
        },
        "provenance_required": [],
        "memory_opportunity": _memory_opportunity(prompt_l, "prompt_routing"),
        "must_not_use": ["executing an irreversible delete", "guessing a delete/remove target",
                         "any low-level or bulk delete tool"],
        "fallback_plan": {"rules": ["prefer a reversible archive/plan over a delete"],
                          "unsafe_fallback_blocked": True, "failure_recovery": ""},
        "route_confidence": "high",
        "routing_rationale": ("Destructive intent detected (delete/remove/wipe/destroy of a stored "
                              "object). Destructive execution is not self-authorized; confirm the exact "
                              "target and prefer a reversible archive plan."),
        "clarifying_question": ("This looks like a destructive request. Deletes are not executed from a "
                                "prompt — confirm the exact target, and note that a reversible archive "
                                "(vault_archive_note_plan / vault_delete_note_plan, which substitutes "
                                "archive) is preferred over an irreversible delete. Proceed?"),
        "preflight_is_read_only": True,
        "destructive_intent": True,
        "constraints": [f"prohibited:{c}" for c in sorted(prohibitions | {"write", "execute"})],
        "warnings": [],
        "next_step": None,
        "additional_steps": [],
        "route": {
            "intent": "destructive", "source_of_truth": "unclassified", "family": "prompt_routing",
            "workflow": "context_preflight", "confidence": "high",
        },
        "freshness": _freshness_view(freshness, is_write=True),
    }


def explain_route(prompt: str, **kwargs: Any) -> dict[str, Any]:
    """Route + attach the full workflow/family records (same normalized route as route_prompt)."""
    plan = route_prompt(prompt, **kwargs)
    wf = workflow_record(plan["recommended_workflow"])
    plan["workflow_detail"] = wf
    plan["family_detail"] = family_record(plan["primary_family"])
    return plan
