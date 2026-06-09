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


@lru_cache(maxsize=1)
def _load_aliases() -> tuple[_Alias, ...]:
    """Load + compile the alias map (longest token first). Empty tuple if the seed is unavailable.

    Advisory: a missing/malformed seed yields no aliases (every item stays unassigned) rather than
    crashing the daily run — project inference is a quality enhancement, not a guardrail.
    """
    override = os.environ.get(_SEED_ENV)
    path = (
        Path(override).expanduser()
        if override
        else PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
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


def resolve_project(*texts: str | None) -> str | None:
    """Return the canonical ``project_key`` inferred from any of ``texts``, or ``None``.

    Checks each text against the alias map (longest alias first); the first match wins. Conservative:
    returns ``None`` when nothing matches (caller keeps the item unassigned).
    """
    aliases = _load_aliases()
    if not aliases:
        return None
    for text in texts:
        if not text:
            continue
        for alias in aliases:
            if alias.pattern.search(text):
                return alias.project_key
    return None


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
