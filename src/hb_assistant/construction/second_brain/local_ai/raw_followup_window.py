"""Phase 10 — bounded, redacted, NON-persisted raw email follow-up window builder + local preview.

Builds an ephemeral, in-process model-input window from the local raw email rows
(``email_message_raw_content``) that back an already source-linked follow-up candidate / watch item.
This module deliberately does **not** reuse :mod:`raw_context` (whose
``build_raw_email_context_packet`` persists a packet row to ``raw_content_model_context_packets``
for audit/replay) — nothing here is ever written to the DB, repo, evidence, logs, browser brief, or
Obsidian brief. The window exists only in memory for the duration of one enrichment call (or a
single explicit operator preview) and is referenced downstream solely by its ``raw_excerpt_hash``.

Hard boundary (see ``reference/RAW_CONTENT_BOUNDARY.md``):

- attachments + attachment text are excluded;
- ``body_html`` is never read (text-only);
- quoted reply chains, signatures, and legal disclaimers are stripped;
- URLs / signed+download URLs / meeting join links / tokens+secrets / phone numbers / email
  addresses are redacted (reusing :func:`packet_normalize.normalize_model_text` for the URL/meeting/
  passcode/dial-in/phone families, plus an email-address pass here);
- per-message, per-thread, and total-character caps bound the window;
- only opaque source aliases + SHA-256[:12] hashes leave this module.

Public entry points (additive, side-effect free):
    sanitize_followup_message_text(body_text, *, max_chars) -> (text, meta)
    build_raw_followup_window(*, candidate_id, candidate_type, source_refs, store, caps=None,
        user_domains=()) -> RawFollowupWindow
    build_raw_local_preview(window, *, opt_in) -> RawLocalPreview   # opt_in MUST be True
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from hb_assistant.procore.normalizers.hashing import hash_summary

from .packet_normalize import normalize_model_text

# Conservative default caps (package Prompt 02). Operators may pass a custom RawWindowCaps.
DEFAULT_MAX_THREADS = 1
DEFAULT_MAX_MESSAGES_PER_THREAD = 6
DEFAULT_MAX_CHARS_PER_MESSAGE = 1500
DEFAULT_MAX_TOTAL_CHARS = 6000
DEFAULT_MAX_SUBJECT_CHARS = 200

# Source families that resolve to local raw email rows.
_EMAIL_SOURCE_FAMILIES = frozenset(
    {
        "email_message",
        "email_thread",
        "email_thread_summary",
        "email_message_raw_content",
        "email_thread_raw_context",
    }
)

# Email-address redaction (the URL/meeting/phone families are handled by normalize_model_text).
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Token / secret / API-key redaction. normalize_model_text strips whole URLs (so signed/download/
# join links and any token in their query string are removed), but bare credentials outside a URL
# need their own pass. Applied BEFORE URL/whitespace normalization.
_TOKEN_PATTERNS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bBearer\s+[A-Za-z0-9._\-]+",
        r"\bAuthorization:\s*\S+",
        r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|"
        r"client[_-]?secret|secret|password|passwd|token|sig|signature)\b\s*[:=]\s*\S+",
        r"\beyJ[A-Za-z0-9._\-]{10,}",            # JWT
        r"\b(?:sk|pk|ghp|gho|xox[bapr])[-_][A-Za-z0-9]{8,}\b",  # provider key prefixes
        r"\bAKIA[0-9A-Z]{12,}\b",                # AWS access key id
    )
)


def _redact_tokens(text: str) -> tuple[str, bool]:
    redacted = False
    for pat in _TOKEN_PATTERNS:
        new = pat.sub("[redacted]", text)
        if new != text:
            redacted = True
            text = new
    return text, redacted

# Quoted-reply / forwarded-header separators — text from the first match onward is dropped.
_QUOTE_SEPARATORS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^\s*on .+ wrote:\s*$",                       # Gmail / Apple "On <date>, X wrote:"
        r"^\s*-{2,}\s*original message\s*-{2,}\s*$",    # Outlook "-----Original Message-----"
        r"^\s*_{5,}\s*$",                               # Outlook divider line
        r"^\s*from:\s.+$",                              # Outlook quoted header block start
        r"^\s*sent:\s.+$",
        r"^\s*-{2,}\s*forwarded message\s*-{2,}\s*$",
        r"^\s*begin forwarded message:\s*$",
    )
)

# Signature / mobile-footer markers — text from the first match onward is dropped.
_SIGNATURE_SEPARATORS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^\s*--\s*$",                                  # RFC 3676 signature delimiter
        r"^\s*sent from my .+$",                        # mobile footer
        r"^\s*(best|kind)\s+regards,?\s*$",
        r"^\s*(thanks|thank you|regards|sincerely|cheers|best),?\s*$",
    )
)

# Legal disclaimer markers — text from the first match onward is dropped.
_DISCLAIMER_MARKERS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"this (e-?mail|message) (and any attachments|is intended|may contain)",
        r"\bconfidential(ity)?\b.*\b(notice|intended recipient|privileged)\b",
        r"if you are not the intended recipient",
        r"please consider the environment before printing",
    )
)


@dataclass(frozen=True)
class RawWindowCaps:
    """Bounded window limits (all enforced; never relaxed by config at runtime)."""

    max_threads: int = DEFAULT_MAX_THREADS
    max_messages_per_thread: int = DEFAULT_MAX_MESSAGES_PER_THREAD
    max_chars_per_message: int = DEFAULT_MAX_CHARS_PER_MESSAGE
    max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS
    max_subject_chars: int = DEFAULT_MAX_SUBJECT_CHARS


@dataclass(frozen=True)
class RawFollowupWindow:
    """An in-memory, bounded, redacted raw follow-up window. Never persisted.

    ``window_text`` is the sanitized model-input text; ``raw_excerpt_hash`` is its stable
    ``sha256:<prefix>`` reference. ``source_aliases`` are opaque, non-content references the model
    may cite; ``message_ref_hashes`` / ``thread_ref_hash`` are hashes only. ``is_persistable`` is a
    hard marker (always False) so callers cannot mistake this for a storable artifact.
    """

    candidate_id: str
    candidate_type: str
    subject_sanitized: str
    window_text: str
    raw_excerpt_hash: str
    source_aliases: list[str]
    message_ref_hashes: list[str]
    thread_ref_hash: Optional[str]
    message_count: int
    caps: RawWindowCaps
    meta: dict[str, Any]
    blockers: list[str] = field(default_factory=list)
    is_persistable: bool = False

    @property
    def available(self) -> bool:
        """True when a non-empty sanitized window was built (at least one resolved message)."""
        return self.message_count > 0 and bool(self.window_text.strip())


@dataclass(frozen=True)
class RawLocalPreview:
    """Bounded, redacted, terminal-only operator preview. Explicit opt-in; never persisted.

    Built only via :func:`build_raw_local_preview` with ``opt_in=True``. Carries a warning banner
    and a hard ``is_persistable=False`` marker; it must never be emitted to JSON, evidence, or logs.
    """

    banner: str
    text: str
    raw_excerpt_hash: str
    is_persistable: bool = False


def _sha256_ref(text: str) -> str:
    """Stable ``sha256:<prefix>`` reference for a string (SHA-256[:12] via the shared helper)."""
    prefix = (hash_summary(text) or {}).get("hash_prefix") or ""
    return f"sha256:{prefix}"


def _redact_emails(text: str) -> tuple[str, bool]:
    new = _EMAIL_RE.sub("[email]", text)
    return new, new != text


def _truncate_first_match(lines: list[str], patterns: tuple[re.Pattern[str], ...]) -> tuple[list[str], bool]:
    """Return lines up to (excluding) the first line matching any pattern, and whether one matched."""
    for idx, line in enumerate(lines):
        if any(p.match(line) for p in patterns):
            return lines[:idx], True
    return lines, False


def sanitize_followup_message_text(
    body_text: Optional[str], *, max_chars: int = DEFAULT_MAX_CHARS_PER_MESSAGE
) -> tuple[str, dict[str, Any]]:
    """Sanitize one raw email ``body_text`` into bounded, redacted model text (pure; no IO).

    Pipeline: drop ``>``-quoted lines → cut at the first quote/forward separator → cut at the first
    signature marker → cut at the first disclaimer marker → redact email addresses → hand off to
    :func:`normalize_model_text` (text-only; ``body_html`` is never passed) for URL/meeting/passcode/
    dial-in/phone/divider/boilerplate redaction + whitespace collapse + truncation to ``max_chars``.
    """
    raw = body_text or ""
    lines = raw.splitlines()
    # Drop fully-quoted lines first (">", ">>", "> ...").
    quote_line_dropped = any(re.match(r"^\s*>", ln) for ln in lines)
    lines = [ln for ln in lines if not re.match(r"^\s*>", ln)]

    lines, quote_cut = _truncate_first_match(lines, _QUOTE_SEPARATORS)
    quotes_stripped = quote_line_dropped or quote_cut
    lines, signatures_stripped = _truncate_first_match(lines, _SIGNATURE_SEPARATORS)
    lines, disclaimers_stripped = _truncate_first_match(lines, _DISCLAIMER_MARKERS)

    pre_redacted = "\n".join(lines)
    pre_redacted, tokens_redacted = _redact_tokens(pre_redacted)
    pre_redacted, emails_redacted = _redact_emails(pre_redacted)

    # text-only: body_html is NEVER passed — HTML is excluded by contract.
    text, norm_meta = normalize_model_text(pre_redacted, None, max_chars=max_chars)

    meta = {
        "quotes_stripped": quotes_stripped,
        "signatures_stripped": signatures_stripped,
        "disclaimers_stripped": disclaimers_stripped,
        "emails_redacted": emails_redacted,
        "tokens_redacted": tokens_redacted,
        "urls_redacted": norm_meta.get("redacted_join_artifacts", False),
        "boilerplate_stripped": norm_meta.get("teams_boilerplate_stripped", False),
        "html_excluded": True,
        "attachments_excluded": True,
        "truncated": norm_meta.get("truncated", False),
        "char_count": norm_meta.get("char_count", len(text)),
    }
    return text, meta


def _resolve_email_rows(
    source_refs: list[dict[str, Any]], store: Any, *, max_messages: int
) -> tuple[list[dict[str, Any]], list[str]]:
    """Resolve email source refs to raw email rows (read-only). Returns (rows, blockers).

    Only refs in an email source family are considered. Resolution prefers the message_id_hash
    (``source_primary_key_hash``); failing that it matches the ref hash against the raw table's
    ``source_ref_hash``. Non-email refs are skipped (recorded as a blocker), never raised.
    """
    blockers: list[str] = []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    fallback_index: Optional[dict[str, dict[str, Any]]] = None

    for ref in source_refs:
        family = str(ref.get("source_family") or "")
        if family not in _EMAIL_SOURCE_FAMILIES:
            blockers.append(f"skipped_non_email_ref:{family or 'unknown'}")
            continue
        pk_hash = ref.get("source_primary_key_hash")
        row: Optional[dict[str, Any]] = None
        if pk_hash:
            row = store.get_email_message_raw_content(message_id_hash=str(pk_hash))
        if row is None:
            ref_hash = ref.get("source_ref_hash")
            if ref_hash:
                if fallback_index is None:
                    fallback_index = {
                        str(r.get("source_ref_hash")): r
                        for r in store.list_email_message_raw_content(limit=100000)
                        if r.get("source_ref_hash")
                    }
                row = fallback_index.get(str(ref_hash))
        if row is None:
            blockers.append("raw_row_unavailable")
            continue
        key = str(row.get("message_id_hash") or row.get("raw_email_id"))
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)

    rows.sort(key=lambda r: str(r.get("received_at_utc") or ""))
    if len(rows) > max_messages:
        rows = rows[-max_messages:]
        blockers.append("messages_capped")
    return rows, blockers


def build_raw_followup_window(
    *,
    candidate_id: str,
    candidate_type: str,
    source_refs: list[dict[str, Any]],
    store: Any,
    caps: Optional[RawWindowCaps] = None,
    user_domains: tuple[str, ...] = (),
) -> RawFollowupWindow:
    """Build a bounded, redacted, NON-persisted raw follow-up window for one candidate/watch item.

    Requires already-source-linked ``source_refs`` (resolves only the email ones). Loads the minimum
    raw rows, sanitizes each, bounds the total, and returns hashes + opaque aliases. Writes nothing.
    A candidate with no email refs / no resolvable raw rows yields an empty window with blockers
    (never an exception) so the engine can degrade cleanly.
    """
    caps = caps or RawWindowCaps()
    if not source_refs:
        return RawFollowupWindow(
            candidate_id=candidate_id,
            candidate_type=candidate_type,
            subject_sanitized="",
            window_text="",
            raw_excerpt_hash=_sha256_ref(""),
            source_aliases=[],
            message_ref_hashes=[],
            thread_ref_hash=None,
            message_count=0,
            caps=caps,
            meta={"reason": "no_source_refs"},
            blockers=["no_source_refs"],
        )

    rows, blockers = _resolve_email_rows(
        source_refs, store, max_messages=caps.max_messages_per_thread
    )
    user_doms = {d.lower() for d in user_domains}

    aliases: list[str] = []
    message_ref_hashes: list[str] = []
    rendered_parts: list[str] = []
    subject_sanitized = ""
    total = 0
    agg_meta: dict[str, Any] = {
        "quotes_stripped": False,
        "signatures_stripped": False,
        "disclaimers_stripped": False,
        "emails_redacted": False,
        "tokens_redacted": False,
        "urls_redacted": False,
        "html_excluded": True,
        "attachments_excluded": True,
        "truncated": False,
    }
    conversation_hashes: set[str] = set()

    _PART_SEP_LEN = 2  # "\n\n" between rendered parts
    for row in rows:
        if total >= caps.max_total_chars:
            blockers.append("total_chars_capped")
            break
        # Subject (allowed local input) — sanitized + bounded, taken from the first/most-recent.
        if not subject_sanitized and row.get("subject"):
            subj, _sm = sanitize_followup_message_text(
                str(row.get("subject")), max_chars=caps.max_subject_chars
            )
            subject_sanitized = subj
        text, meta = sanitize_followup_message_text(
            row.get("body_text"), max_chars=caps.max_chars_per_message
        )
        if not text.strip():
            continue
        msg_hash = str(row.get("message_id_hash") or row.get("raw_email_id") or "")
        alias = f"email_msg:{msg_hash[:12]}" if msg_hash else f"email_msg:{len(aliases)}"
        from_dom = ""
        addr = row.get("from_address")
        if isinstance(addr, str) and "@" in addr:
            from_dom = addr.split("@", 1)[1].lower()
        direction = "from_me" if (from_dom and from_dom in user_doms) else "from_other"
        header = (
            f"[{alias}] received_at={row.get('received_at_utc') or '(none)'} "
            f"direction={direction}\n"
        )
        sep = _PART_SEP_LEN if rendered_parts else 0
        # Bound the FULL assembled window_text (headers included) to max_total_chars.
        budget = caps.max_total_chars - total - sep - len(header)
        if budget <= 0:
            blockers.append("total_chars_capped")
            break
        if len(text) > budget:
            text = text[:budget].rstrip()
            agg_meta["truncated"] = True
            blockers.append("total_chars_capped")
        part = header + text
        rendered_parts.append(part)
        aliases.append(alias)
        if msg_hash:
            message_ref_hashes.append(msg_hash)
        if row.get("conversation_id_hash"):
            conversation_hashes.add(str(row.get("conversation_id_hash")))
        total += sep + len(part)
        for k in ("quotes_stripped", "signatures_stripped", "disclaimers_stripped",
                  "emails_redacted", "tokens_redacted", "urls_redacted"):
            agg_meta[k] = agg_meta[k] or meta.get(k, False)

    window_text = "\n\n".join(rendered_parts)
    thread_ref_hash = (
        _sha256_ref("|".join(sorted(conversation_hashes))) if conversation_hashes else None
    )
    agg_meta["message_count"] = len(aliases)
    agg_meta["char_count"] = len(window_text)
    # V49 Pass 2: tag with the best structured-projection source-quality backing this window
    # (prefer structured; a lower-quality row never sets a higher tag).
    try:
        from hb_assistant.construction.email_calendar.source_quality import rank as _sq_rank

        best_sq = None
        for r in rows:
            sj = store.get_email_message_structured(message_id_hash=r.get("message_id_hash"))
            if sj and _sq_rank(sj.get("source_quality")) > _sq_rank(best_sq):
                best_sq = sj.get("source_quality")
        agg_meta["structured_source_quality"] = best_sq
        agg_meta["structured_projection_backed"] = best_sq is not None
    except Exception:
        pass
    if not rendered_parts and "no_source_refs" not in blockers:
        blockers.append("no_raw_content_available")

    return RawFollowupWindow(
        candidate_id=candidate_id,
        candidate_type=candidate_type,
        subject_sanitized=subject_sanitized,
        window_text=window_text,
        raw_excerpt_hash=_sha256_ref(f"{subject_sanitized}\n{window_text}"),
        source_aliases=aliases,
        message_ref_hashes=message_ref_hashes,
        thread_ref_hash=thread_ref_hash,
        message_count=len(aliases),
        caps=caps,
        meta=agg_meta,
        blockers=sorted(set(blockers)),
    )


_PREVIEW_BANNER = (
    "⚠ RAW-LOCAL PREVIEW — local terminal only. Bounded + redacted. "
    "NEVER copy into evidence, docs, logs, commits, or the daily brief. Not persisted."
)


def build_raw_local_preview(window: RawFollowupWindow, *, opt_in: bool) -> RawLocalPreview:
    """Return a bounded, redacted, terminal-only preview of ``window``. Requires ``opt_in=True``.

    This is the ONLY way to surface the sanitized window text to an operator. Callers must pass
    ``opt_in=True`` explicitly (the CLI maps ``--show-raw-local`` to it); otherwise this raises so a
    preview can never be produced implicitly. The returned object is marked non-persistable.
    """
    if opt_in is not True:
        raise ValueError("raw-local preview requires explicit opt_in=True")
    body = window.window_text.strip() or "(no sanitized content available)"
    subj = window.subject_sanitized.strip()
    text = (f"subject: {subj}\n\n" if subj else "") + body
    return RawLocalPreview(
        banner=_PREVIEW_BANNER,
        text=text,
        raw_excerpt_hash=window.raw_excerpt_hash,
    )
