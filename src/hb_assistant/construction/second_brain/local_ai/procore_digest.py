"""Phase 10 — deterministic Procore action-signal digest (advisory, no writeback).

Composes the existing redacted, read-only Procore rollup builders into a reviewable,
source-linked per-project digest of open action signals, and (optionally, capped)
persists per-group rollup candidates into ``daily_brief_action_candidates`` so the
digest can feed the daily-brief / review layer.

Deterministic-first: counts/grouping/overdue come from ``list_procore_action_signals``
(safe enums/ids only — never title/summary/metadata free-text). ``now_utc`` is passed in
by the caller (no clock read), so overdue classification is reproducible. An optional
headline (``build_operational_digest``) and risk terms (``get_procore_text_intelligence``,
``risk_terms_json``/``topics_json`` only) enrich each project, each guarded so a missing
auxiliary read model never breaks the digest.

Safety: no Procore/Graph/external writeback, no cloud LLM. Never exposes ``metadata_json``,
``encrypted_full_text_ref``, ``text_hash``, raw bodies, or signed/download URLs. The optional
``--synthesize`` narrative is fed ONLY already-redacted aggregates (counts + risk keywords),
is advisory and in-memory (never persisted), and fails closed to the deterministic digest.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

_SYNTH_SYSTEM = (
    "You are a construction project assistant. Using ONLY the redacted aggregate counts and "
    "risk keywords provided, write a brief advisory summary (3-5 sentences) and a short list "
    "of risk flags. Do not invent specific records, names, amounts, or dates. Respond with "
    'JSON only: {"narrative": "<text>", "risk_flags": ["<flag>", ...]}.'
)

# Priority by the highest importance present in a signal-type group (lower = surfaced first).
_IMPORTANCE_PRIORITY = {"high": 10, "medium": 50, "low": 90}


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe_json_list(blob: Any) -> list[str]:
    """Parse a JSON array of strings defensively; return [] on anything unexpected."""
    if not blob or not isinstance(blob, str):
        return []
    try:
        data = json.loads(blob)
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [str(x) for x in data if isinstance(x, (str, int, float))]


def _dimensions_for_signal(signal_type: str) -> list[str]:
    """Classify a signal_type into risk dimensions, reusing the existing keyword map."""
    try:
        from hb_assistant.store.procore_project_health import _dimensions_for

        return list(_dimensions_for(signal_type))
    except Exception:
        return []


def _project_headline(project_key: str, *, now_utc: str, db_path: Optional[Path]) -> dict[str, Any]:
    """Optional richer headline from build_operational_digest; guarded (never raises)."""
    try:
        from hb_assistant.store.procore_operational import build_operational_digest

        digest = build_operational_digest(project_key, now_utc=now_utc, db_path=db_path)
        return {
            "ok": True,
            "health_status": digest.get("health_status"),
            "headline": digest.get("headline"),
        }
    except Exception as e:  # auxiliary read models may be unpopulated on some DBs
        return {"ok": False, "reason": f"headline_unavailable: {type(e).__name__}"}


def _project_risk_terms(project_key: str, *, db_path: Optional[Path], max_terms: int) -> list[str]:
    """Bounded, de-duplicated risk keywords from text intelligence; guarded (never raises)."""
    try:
        from hb_assistant.store.procore_enrichment import get_procore_text_intelligence

        rows = get_procore_text_intelligence(project_key=project_key, db_path=db_path)
    except Exception:
        return []
    seen: dict[str, None] = {}
    for r in rows:
        for term in _safe_json_list(r.get("risk_terms_json")):
            seen.setdefault(term, None)
            if len(seen) >= max_terms:
                return list(seen)
    return list(seen)


def build_procore_action_digest(
    *,
    store: Any,
    now_utc: str,
    db_path: Optional[str] = None,
    project_key: Optional[str] = None,
    limit: int = 50,
    dry_run: bool = True,
    max_persist: Optional[int] = None,
    synthesize: bool = False,
    client: Any = None,
    max_source_refs: int = 5,
    max_risk_terms: int = 10,
) -> dict[str, Any]:
    """Build a deterministic, source-linked Procore action-signal digest.

    Dry-run is the default (zero writes). ``--apply`` (dry_run=False) requires ``max_persist``
    and caps ACTUAL ``daily_brief_action_candidates`` inserts; once the cap is hit, remaining
    new groups are counted (``would_persist``) but not written. Persisted rows are idempotent
    per (brief_date, section, project|signal_type). No raw content, no writeback.
    """
    if not dry_run and max_persist is None:
        raise ValueError("apply requires max_persist (cap on actual persisted candidates)")

    dbp = Path(db_path) if db_path else None
    brief_date = now_utc[:10]
    section = "procore"

    # Safe enums/ids only — never title/summary/metadata free-text.
    signals = store.list_procore_action_signals(
        project_key=project_key, signal_status="open", limit=100000
    )

    projects = (
        [project_key] if project_key else sorted({str(s.get("project_key")) for s in signals})
    )

    # Existing candidates for this brief_date+section (idempotent dedup accounting).
    existing_ids = {
        str(r.get("daily_brief_action_candidate_id"))
        for r in store.list_daily_brief_action_candidates(
            brief_date=brief_date, section=section, limit=100000
        )
    }

    by_importance_global: dict[str, int] = {}
    overdue_total = 0
    project_views: list[dict[str, Any]] = []
    # Flat group list for deterministic apply ordering.
    all_groups: list[dict[str, Any]] = []

    for proj in projects:
        proj_signals = [s for s in signals if str(s.get("project_key")) == proj]
        groups: dict[str, dict[str, Any]] = {}
        for s in proj_signals:
            st = str(s.get("signal_type"))
            imp = str(s.get("importance") or "medium")
            by_importance_global[imp] = by_importance_global.get(imp, 0) + 1
            g = groups.setdefault(
                st,
                {
                    "project_key": proj,
                    "signal_type": st,
                    "count": 0,
                    "overdue": 0,
                    "by_importance": {},
                    "dimensions": _dimensions_for_signal(st),
                    "source_refs": [],
                },
            )
            g["count"] += 1
            g["by_importance"][imp] = g["by_importance"].get(imp, 0) + 1
            due = _parse_dt(s.get("due_at_utc"))
            now_dt = _parse_dt(now_utc)
            if due is not None and now_dt is not None and due < now_dt:
                g["overdue"] += 1
                overdue_total += 1
            if len(g["source_refs"]) < max_source_refs:
                g["source_refs"].append(
                    {
                        "action_signal_id": s.get("action_signal_id"),
                        "record_key": s.get("record_key"),
                        "endpoint_id": s.get("endpoint_id"),
                    }
                )

        group_list = sorted(groups.values(), key=lambda g: (-g["count"], g["signal_type"]))
        all_groups.extend(group_list)
        project_views.append(
            {
                "project_key": proj,
                "open_signal_count": len(proj_signals),
                "group_count": len(group_list),
                "headline": _project_headline(proj, now_utc=now_utc, db_path=dbp),
                "risk_terms": _project_risk_terms(proj, db_path=dbp, max_terms=max_risk_terms),
                "groups": group_list[:limit],
            }
        )

    # Deterministic apply ordering: highest-count groups first across projects.
    all_groups.sort(key=lambda g: (-g["count"], g["project_key"], g["signal_type"]))

    summary: dict[str, Any] = {
        "projects": len(projects),
        "groups": len(all_groups),
        "total_open_signals": len(signals),
        "by_importance": dict(sorted(by_importance_global.items())),
        "overdue_total": overdue_total,
        "would_persist": 0,
        "persisted": 0,
        "skipped_existing": 0,
    }
    remaining: Optional[int] = max_persist if (not dry_run and max_persist is not None) else None

    for g in all_groups:
        group_key = f"{g['project_key']}|{g['signal_type']}"
        row_id = store.daily_brief_action_candidate_id_for(brief_date, section, group_key)
        if row_id in existing_ids:
            summary["skipped_existing"] += 1
            continue
        summary["would_persist"] += 1
        if dry_run or (remaining is not None and remaining <= 0):
            continue
        # Highest importance present in the group → priority.
        imp = (
            "high"
            if g["by_importance"].get("high")
            else ("medium" if g["by_importance"].get("medium") else "low")
        )
        overdue_note = f" ({g['overdue']} overdue)" if g["overdue"] else ""
        title = f"{g['count']} open {g['signal_type']} signals{overdue_note}"
        reason = ",".join(g["dimensions"]) or "open_action_signals"
        inserted = store.insert_daily_brief_action_candidate(
            brief_date=brief_date,
            section=section,
            title_redacted=title,
            confidence=1.0,
            project_key=g["project_key"],
            priority=_IMPORTANCE_PRIORITY.get(imp, 50),
            reason_redacted=reason,
            recommended_next_action="review",
            group_key=group_key,
        )
        if inserted:
            summary["persisted"] += 1
            existing_ids.add(row_id)
            if remaining is not None:
                remaining -= 1
        else:
            summary["skipped_existing"] += 1

    synthesis = _maybe_synthesize(synthesize=synthesize, client=client, project_views=project_views)

    return {
        "command": "second-brain procore-digest build",
        "ok": True,
        "applied": not dry_run,
        "now_utc": now_utc,
        "brief_date": brief_date,
        "project_filter": project_key,
        "summary": summary,
        "projects": project_views,
        "synthesis": synthesis,
        "guardrails": {
            "dry_run_default": True,
            "apply_requires_max_persist": True,
            "deterministic_no_clock": True,
            "source_linked_only": True,
            "no_raw_persistence": True,
            "no_procore_writeback": True,
            "no_external_writeback": True,
            "no_cloud_llm": True,
            "advisory_only": True,
        },
    }


def _redacted_aggregate(project_views: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the ONLY thing fed to the optional model: counts + risk keywords, no content."""
    agg: list[dict[str, Any]] = []
    for pv in project_views:
        agg.append(
            {
                "project_key": pv["project_key"],
                "open_signal_count": pv["open_signal_count"],
                "signal_type_counts": {g["signal_type"]: g["count"] for g in pv["groups"]},
                "risk_terms": pv["risk_terms"],
            }
        )
    return agg


def _maybe_synthesize(
    *, synthesize: bool, client: Any, project_views: list[dict[str, Any]]
) -> dict[str, Any]:
    """Optional bounded advisory narrative (off by default; in-memory only; fails closed)."""
    if not synthesize:
        return {"requested": False}
    if client is None:
        return {"requested": True, "ok": False, "reason": "no_local_model_client"}
    payload = _redacted_aggregate(project_views)
    try:
        raw = client.generate_json(system=_SYNTH_SYSTEM, prompt=json.dumps(payload))
        data = json.loads(raw)
        narrative = str(data.get("narrative") or "")[:2000]
        flags = [str(x) for x in (data.get("risk_flags") or []) if isinstance(x, (str, int, float))]
        return {"requested": True, "ok": True, "narrative": narrative, "risk_flags": flags[:20]}
    except Exception as e:
        return {"requested": True, "ok": False, "reason": f"synthesis_failed: {type(e).__name__}"}
