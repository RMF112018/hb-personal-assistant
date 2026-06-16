"""Phase 10 correction — deterministic project inference from free-text tokens.

Resolves an HB ``project_key`` from calendar/email/Procore free text using a config-backed alias
map (``resources/config/project_aliases.seed.yaml``). Inference is deterministic and conservative:

- case-insensitive, **word-boundary** aware (so ``Hilltop`` never matches inside ``hilltops``);
- **longest alias wins** (``Alton Hilltop`` beats ``Hilltop``); both still map to one canonical key;
- **no match → ``None``** (the caller keeps the item unassigned → "Needs Project Review"); the
  resolver never invents a low-confidence project.

The canonical ``project_key`` values match the Procore mapping
(``resources/config/procore_projects.seed.yaml``) so an inferred key is consistent across systems.

Also provides lightweight **diagnostics** (:func:`summarize_unresolved_tokens`) so frequently
unresolved tokens can be reviewed and added to the seed, improving alias coverage over time.

Read-only: no DB, no writeback, no network. Operates on already-redacted text only.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from hb_assistant.config.path_policy import PathPolicy

_SEED_RELATIVE = Path("resources") / "config" / "project_aliases.seed.yaml"
_SEED_ENV = "HB_PROJECT_ALIASES"

# Candidate "project-looking" tokens for diagnostics: capitalized words/phrases or ALLCAPS acronyms.
_CANDIDATE_TOKEN_RE = re.compile(r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*|[A-Z]{2,})\b")

# Generic words to ignore when reporting unresolved tokens (reduce diagnostic noise).
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "meeting",
        "call",
        "review",
        "weekly",
        "daily",
        "oac",
        "rfi",
        "rfis",
        "submittal",
        "submittals",
        "team",
        "teams",
        "zoom",
        "lunch",
        "pto",
        "out",
        "office",
        "hold",
        "tentative",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
    }
)


@dataclass(frozen=True)
class _Alias:
    token_lower: str
    project_key: str
    pattern: re.Pattern[str]


def _seed_path() -> Path:
    """Resolve the alias seed path (env override, else repo ``resources/config``)."""
    override = os.environ.get(_SEED_ENV)
    if override:
        return Path(override).expanduser()
    return PathPolicy().resolve_repo_root() / _SEED_RELATIVE


@lru_cache(maxsize=1)
def _load_display_names() -> dict[str, str]:
    """Map canonical ``project_key`` → seed ``display_name`` (empty when the seed is unavailable).

    The same seed that backs alias inference also carries a human ``display_name`` per project, so the
    user-facing brief can show "Alton Hilltop at PBG" instead of the ``alton-hilltop-pbg`` key. A
    missing/malformed seed yields an empty map (callers fall back to the identity store / title-case).
    """
    try:
        data = yaml.safe_load(_seed_path().read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for entry in data.get("projects", []) or []:
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("project_key") or "").strip()
        name = str(entry.get("display_name") or "").strip()
        if key and name:
            out[key] = name
    return out


def _titlecase_slug(project_key: str) -> str:
    """Clean a raw ``project_key`` slug into a readable label (never a bare lowercase slug)."""
    words = re.split(r"[-_\s]+", project_key.strip())
    return " ".join(w[:1].upper() + w[1:] for w in words if w)


def project_display_name(project_key: str | None, *, store: object | None = None) -> str | None:
    """Readable project name for a canonical ``project_key`` (never a raw lowercase slug).

    Resolution order: (1) the seed ``display_name``; (2) the construction project-identity store's
    ``project_name_raw``/``project_name_normalized`` when a ``store`` is supplied; (3) a cleaned,
    title-cased form of the slug. Returns ``None`` for empty input or internal sentinels
    (``__needs_review__`` / ``__internal_*``) so the caller emits a safe label instead.
    """
    pk = str(project_key or "").strip()
    if not pk or pk.startswith("__"):
        return None
    seed = _load_display_names().get(pk)
    if seed:
        return seed
    if store is not None:
        getter = getattr(store, "get_project_identity", None)
        if callable(getter):
            try:
                rec = getter(pk)
            except Exception:
                rec = None
            if rec:
                name = str(rec.get("project_name_raw") or "").strip() or str(
                    rec.get("project_name_normalized") or ""
                ).strip()
                if name:
                    return name
    return _titlecase_slug(pk)


@lru_cache(maxsize=1)
def _load_aliases() -> tuple[_Alias, ...]:
    """Load + compile the alias map (longest token first). Empty tuple if the seed is unavailable.

    Advisory: a missing/malformed seed yields no aliases (every item stays unassigned) rather than
    crashing the daily run — project inference is a quality enhancement, not a guardrail.
    """
    try:
        data = yaml.safe_load(_seed_path().read_text(encoding="utf-8"))
    except Exception:
        return ()
    if not isinstance(data, dict):
        return ()
    aliases: list[_Alias] = []
    for entry in data.get("projects", []) or []:
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("project_key") or "").strip()
        if not key:
            continue
        for token in entry.get("aliases", []) or []:
            tok = str(token).strip()
            if not tok:
                continue
            # Word-boundary match around the (escaped) token; case-insensitive.
            pattern = re.compile(rf"(?<!\w){re.escape(tok)}(?!\w)", re.IGNORECASE)
            aliases.append(_Alias(token_lower=tok.lower(), project_key=key, pattern=pattern))
    # Longest token first so the most specific alias wins.
    aliases.sort(key=lambda a: len(a.token_lower), reverse=True)
    return tuple(aliases)


def resolve_project_alias(*texts: str | None) -> tuple[str | None, str | None]:
    """Return ``(project_key, matched_alias_token)`` inferred from any of ``texts``, or ``(None, None)``.

    The single canonical alias-matching implementation (longest alias first, word-boundary aware,
    case-insensitive; first match wins). :func:`resolve_project` delegates here so callers that also
    need the matched alias token (e.g. calendar category resolution) never re-implement matching.
    """
    aliases = _load_aliases()
    if not aliases:
        return (None, None)
    for text in texts:
        if not text:
            continue
        for alias in aliases:
            if alias.pattern.search(text):
                return (alias.project_key, alias.token_lower)
    return (None, None)


def resolve_project(*texts: str | None) -> str | None:
    """Return the canonical ``project_key`` inferred from any of ``texts``, or ``None``.

    Checks each text against the alias map (longest alias first); the first match wins. Conservative:
    returns ``None`` when nothing matches (caller keeps the item unassigned). Thin wrapper over
    :func:`resolve_project_alias` (single matching implementation).
    """
    return resolve_project_alias(*texts)[0]


def candidate_tokens(text: str | None) -> list[str]:
    """Project-looking tokens in ``text`` (capitalized phrases / acronyms), minus generic stopwords."""
    if not text:
        return []
    out: list[str] = []
    for m in _CANDIDATE_TOKEN_RE.finditer(text):
        tok = m.group(1).strip()
        if tok and tok.lower() not in _STOPWORDS and len(tok) > 1:
            out.append(tok)
    return out


def summarize_unresolved_tokens(
    texts: list[str | None], *, top: int = 10
) -> list[dict[str, object]]:
    """Diagnostic: most frequent project-looking tokens that did NOT resolve to a project.

    Helps the operator extend ``project_aliases.seed.yaml``. Returns ``[{token, count}]`` (capped).
    Tokens are already-redacted free text (titles/locations); no raw bodies, URLs, or addresses.
    """
    counter: Counter[str] = Counter()
    for text in texts:
        if not text or resolve_project(text) is not None:
            continue
        for tok in candidate_tokens(text):
            counter[tok] += 1
    return [{"token": tok, "count": count} for tok, count in counter.most_common(max(0, top))]
