"""Phase 10 — production-like daily run wrapper (Checkpoint 6).

Wraps the proven local-agent pipeline into one repeatable daily operating workflow that the
launchd schedule fires at 5:00 AM on weekdays. It:

1. resolves the weekday-aware date window (central policy — :mod:`daily_brief_window`), including
   weekend skip vs Saturday catch-up of a missed Friday;
2. runs the pipeline (apply, conservative caps) with that window so every stage uses policy dates;
3. renders the raw brief into two **private local consumption surfaces** — a governed Obsidian
   note and a polished self-contained browser HTML file — at stable, **non-repo** paths, and
   converges the raw-free V45 pending email follow-up section onto both surfaces (and a redacted
   count into the status file) whenever pending review-safe rows exist;
4. writes a redacted machine-readable status file every run; and
5. preserves the last *successful* browser brief on failure (never clobbers last-good with a
   failed/partial/unsafe output), writing a degraded "attempted" brief only when safe.

Boundaries: raw content reaches only the Obsidian note + browser HTML (never the status file,
persisted candidate rows, repo, logs, or evidence). The browser HTML is scrubbed + escaped +
fail-closed egress-scanned before write. Output dirs inside the repo are refused. No browser is
auto-opened. No external/Graph/Procore/calendar writeback. Dry-run persists nothing.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from datetime import timezone as _dt_tz  # aliased: the run fn has a `timezone: str` parameter
from pathlib import Path
from typing import Any, Optional

from hb_assistant.config.path_policy import PathPolicy

from .daily_brief_window import DailyBriefWindow, compute_daily_brief_window
from .daily_run_html import render_daily_run_html, scan_daily_run_html
from .pipeline import run_local_agent_pipeline
from .vault_brief_policy import VaultBriefPolicyError, assert_not_legacy, governed_brief_dir

_STATUS_SUBDIR = "daily-run-status"
_LATEST_STATUS = "latest-status.json"
_LAST_SUCCESSFUL = "last-successful.json"
_BROWSER_LATEST = "daily-brief-latest.html"
_BROWSER_LATEST_DETERMINISTIC = "daily-brief-latest-deterministic.html"
_BROWSER_ATTEMPTED = "daily-brief-latest-attempted.html"

# Explicit daily-run result class for a deterministic-useful brief whose local-model synthesis
# degraded: operator-usable (usefulness gate passed) but NOT a full-synthesis success. Distinct from
# "partial" (a non-synthesis stage failed) and "degraded" (usefulness gate failed / unusable).
STATUS_DETERMINISTIC_FALLBACK = "deterministic_success_synthesis_degraded"


def _parse_run_dt(now_utc: str) -> datetime:
    return datetime.fromisoformat(now_utc.replace("Z", "+00:00"))


def _redact_path(p: Path) -> str:
    """Path relative to home (``~/…``) so status files never carry absolute operator paths."""
    try:
        return "~/" + str(p.resolve().relative_to(Path.home()))
    except ValueError:
        return p.name


def _is_in_repo(p: Path) -> bool:
    try:
        repo_root = PathPolicy().resolve_repo_root().resolve()
    except Exception:
        return False
    resolved = p.resolve()
    return resolved == repo_root or repo_root in resolved.parents


def _atomic_write(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / f".{target.name}.tmp"
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(target)


def _render_md_appendix(sections: list[dict[str, Any]]) -> str:
    """Compact, source-linked audit appendix from the deterministic brief sections (no H1/disclaimer).

    This is the hybrid brief's traceability tail — it lists the redacted candidate rows backing the
    synthesized narrative, never the raw technical relationship rows (those are folded into the
    narrative's "What Changed"/"Needs Review" by the model)."""
    if not sections:
        return "_No source-linked candidates for this date._\n"
    lines: list[str] = []
    for sec in sections:
        items = sec.get("items") or []
        if not items:
            continue
        lines.append(
            f"### {sec.get('display', 'Section')} ({sec.get('section_count', len(items))})"
        )
        for it in items:
            title = str(it.get("display_title") or it.get("title_redacted") or "(untitled)")
            parts: list[str] = []
            if it.get("project_key"):
                parts.append(f"project:{it['project_key']}")
            if it.get("recommended_next_action"):
                parts.append(f"next:{it['recommended_next_action']}")
            if it.get("candidate_id"):
                parts.append(f"id:{it['candidate_id']}")
            suffix = f" — {' · '.join(parts)}" if parts else ""
            lines.append(f"- {title}{suffix}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _git_head_short() -> Optional[str]:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(PathPolicy().resolve_repo_root()),
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or None if out.returncode == 0 else None
    except Exception:
        return None


def _read_last_successful_date(status_dir: Path) -> Optional[str]:
    try:
        data = json.loads((status_dir / _LAST_SUCCESSFUL).read_text(encoding="utf-8"))
        d = data.get("brief_date")
        return str(d) if d else None
    except Exception:
        return None


def _stamp(now_utc: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in now_utc)[:32]


def _aggregate_skips(skipped: list[dict[str, Any]]) -> dict[str, int]:
    """Count enrichment skips by reason (raw-free; reason codes only)."""
    counts: dict[str, int] = {}
    for s in skipped or []:
        reason = str(s.get("reason") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def _run_email_raw_enrichment_stage(
    *,
    store: Any,
    now_utc: str,
    enabled: bool,
    dry_run: bool,
    max_persist: Optional[int],
    backend: Any = None,
    present_models: set[str] | None = None,
) -> dict[str, Any]:
    """Bounded, capped, idempotent, source-linked V45 email raw enrichment stage (fail-closed).

    Runs only when ``enabled``. Dry-run reports ``would_persist`` but writes nothing. Apply persists
    review-safe rows capped by ``max_persist`` (idempotent; never raw body/prompt/response). Returns a
    raw-free stage receipt. Never raises into the deterministic run — any error degrades to a receipt.
    """
    receipt: dict[str, Any] = {
        "stage": "email_followup_raw_enrichment",
        "status": "skipped",
        "mode": "dry_run" if dry_run else "apply",
        "enabled": bool(enabled),
        "eligible": 0,
        "would_persist": 0,
        "persisted": 0,
        "skipped_by_reason": {},
        "degraded_reason": None,
        "warnings": [],
    }
    if not enabled:
        receipt["degraded_reason"] = "disabled"
        return receipt
    # Apply requires a positive cap (defense-in-depth; the engine also enforces this).
    if not dry_run and (max_persist is None or max_persist <= 0):
        receipt["status"] = "skipped"
        receipt["degraded_reason"] = "no_cap"
        receipt["warnings"].append("email_raw_enrichment_skipped: apply requires a positive cap")
        return receipt
    try:
        from .email_followup_enrichment import run_email_followup_enrichment

        # Probe installed local models only in production (no injected backend, no explicit set).
        if backend is None and present_models is None:
            try:
                from .provider import build_local_model_status

                status = build_local_model_status(provider_name="ollama")
                present_models = (
                    {str(m) for m in (status.get("present_models") or [])}
                    if status.get("daemon_reachable")
                    else None
                )
            except Exception:
                present_models = None

        res = run_email_followup_enrichment(
            store=store,
            now_utc=now_utc,
            dry_run=dry_run,
            max_persist=None if dry_run else max_persist,
            present_models=present_models,
            backend=backend,
        )
        eligible = int(res.get("eligible") or 0)
        would = int(res.get("would_persist") or 0)
        persisted = int(res.get("persisted") or 0)
        skipped_by_reason = _aggregate_skips(res.get("skipped") or [])
        model_unavailable = bool(res.get("model_unavailable"))
        if eligible == 0:
            status_code = "skipped"
            degraded_reason = res.get("note") or "no_eligible_candidates"
        elif model_unavailable and persisted == 0 and would == 0:
            status_code = "degraded"
            degraded_reason = "local_model_unavailable"
        else:
            status_code = "ok"
            degraded_reason = None
        receipt.update(
            status=status_code,
            eligible=eligible,
            would_persist=would,
            persisted=persisted,
            skipped_by_reason=skipped_by_reason,
            degraded_reason=degraded_reason,
        )
    except Exception as exc:  # advisory-only — never fail the deterministic run
        receipt["status"] = "failed"
        receipt["degraded_reason"] = f"stage_error:{type(exc).__name__}"
        receipt["warnings"].append(f"email_raw_enrichment_stage_error:{type(exc).__name__}")
    return receipt


def run_daily_local_agent(
    *,
    store: Any,
    now_utc: str,
    timezone: str = "America/New_York",
    db_path: Optional[str] = None,
    dry_run: bool = True,
    max_persist_per_stage: Optional[int] = 10,
    max_total_persist: Optional[int] = 30,
    limit: int = 50,
    lookahead_days: int = 14,
    include_raw: bool = True,
    weekdays_only: bool = True,
    write_obsidian: bool = False,
    confirm_vault_write: bool = False,
    vault_brief_dir: Optional[str] = None,
    generate_browser: bool = True,
    browser_output_dir: Optional[str] = None,
    status_dir: Optional[str] = None,
    last_successful_date: Optional[str] = None,
    synthesize_brief: bool = False,
    synthesis_profile_id: str = "brief_synthesis",
    synthesis_backend: Any = None,
    include_relationship_candidates: bool = False,
    relationship_scan_threads: Optional[int] = None,
    relationship_scan_events: Optional[int] = None,
    model_enriched_intelligence: bool = False,
    model_enriched_backend: Any = None,
    model_enriched_present_models: set[str] | None = None,
    email_raw_enrichment: bool = False,
    email_raw_enrichment_max_persist: Optional[int] = None,
    email_raw_enrichment_backend: Any = None,
    email_raw_enrichment_present_models: set[str] | None = None,
) -> dict[str, Any]:
    """Run the daily local-agent workflow once. Dry-run by default; see module docstring.

    ``model_enriched_intelligence`` / ``email_raw_enrichment`` default off at the FUNCTION level (so
    direct callers/tests opt in explicitly, mirroring ``synthesize_brief``); the CLI and the installed
    scheduler set them ON by default — Model Enriched Intelligence is the default-on operator behavior
    for ``second-brain daily-run run`` and scheduled runs, with ``--no-model-enriched-intelligence``
    to disable.

    ``include_relationship_candidates`` (default off → the scheduled run is unchanged) opts the
    cross-source relationship-candidate stage into the pipeline, just before render, so relationship
    rows are populated and the brief's "Related Context" section is surfaced automatically.
    ``relationship_scan_threads`` / ``relationship_scan_events`` widen that stage's scan window
    (default None → the stage's own 50/50 defaults); they only matter when the stage is opted in.
    """
    cmd = "second-brain daily-run run"
    started_wall_utc = datetime.now(_dt_tz.utc).isoformat()
    policy = PathPolicy()
    browser_dir = Path(browser_output_dir) if browser_output_dir else policy.get_html_dir()
    status_d = Path(status_dir) if status_dir else (policy.get_app_support() / _STATUS_SUBDIR)

    # Effective governed brief folder for the SCHEDULED daily-run: the explicit ``vault_brief_dir``
    # override, else the policy-declared governed folder (``Work/Daily Brief``) — NEVER the legacy
    # Phase 08A folder. Fail-closed if the policy can't resolve or a legacy folder is requested, so a
    # scheduled run can never silently fall back to the wrong folder. (The separate Phase 08A/09
    # MCP-handoff brief keeps its own default via daily_brief.output.resolve_brief_path.)
    try:
        effective_vault_dir = (
            Path(vault_brief_dir) if vault_brief_dir else governed_brief_dir(path_policy=policy)
        )
        assert_not_legacy(effective_vault_dir)
    except VaultBriefPolicyError as exc:
        return _failure_receipt(cmd, "vault_brief_dir_refused", detail=str(exc)[:120])
    vault_brief_dir = str(effective_vault_dir)
    vault_brief_dir_redacted = _redact_path(effective_vault_dir)

    # Repo-containment guard — generated raw outputs must never land inside the repo.
    for label, d in (("browser_output_dir", browser_dir), ("status_dir", status_d)):
        if _is_in_repo(d):
            return _failure_receipt(cmd, "output_path_inside_repo_refused", detail=label)
    if vault_brief_dir is not None and _is_in_repo(Path(vault_brief_dir)):
        return _failure_receipt(cmd, "output_path_inside_repo_refused", detail="vault_brief_dir")

    if last_successful_date is None:
        last_successful_date = _read_last_successful_date(status_d)

    window = compute_daily_brief_window(
        _parse_run_dt(now_utc), timezone, last_successful_date=last_successful_date
    )
    brief_date = window.run_date

    # Weekend skip: write a status file, preserve last-good, do nothing else.
    if weekdays_only and window.is_skipped_weekend:
        status_path = _write_status(
            status_d,
            now_utc,
            status="skipped_weekend",
            window=window,
            pipeline=None,
            outputs={},
            warnings=[window.explanation],
            failure_reason=None,
            is_success=False,
        )
        return {
            "command": cmd,
            "ok": True,
            "status": "skipped_weekend",
            "partial": False,
            "dry_run": dry_run,
            "brief_date": brief_date,
            "brief_freshness": "skipped",
            "date_policy": window.to_dict(),
            "warnings": [window.explanation],
            "outputs": {
                "status_path": _redact_path(status_path),
                "vault_brief_dir_redacted": vault_brief_dir_redacted,
            },
            "egress_scan": {"clean": True, "matched_labels": []},
            "guardrails": _guardrails(include_raw, dry_run, generate_browser),
        }

    # The pipeline keys its brief_date off now_utc[:10]; align it to the resolved target date
    # (e.g. a Saturday catch-up resolves to Friday). The explicit window drives calendar dates.
    pipeline_now = window.lookback_end  # target run datetime, ISO with local offset

    pipeline = run_local_agent_pipeline(
        store=store,
        now_utc=pipeline_now,
        db_path=db_path,
        dry_run=dry_run,
        max_persist_per_stage=max_persist_per_stage,
        max_total_persist=max_total_persist,
        limit=limit,
        lookahead_days=lookahead_days,
        include_raw=include_raw,
        window=window,
        include_relationship_candidates=include_relationship_candidates,
        relationship_scan_threads=relationship_scan_threads,
        relationship_scan_events=relationship_scan_events,
    )

    brief = pipeline.get("brief") or {}
    sections = brief.get("sections") or []
    summary = brief.get("summary") or {}
    markdown = str(brief.get("markdown") or "")
    warnings = list(pipeline.get("warnings") or [])
    render_failed = any(
        r.get("stage") == "daily_brief_render" and r.get("status") == "failed"
        for r in pipeline.get("stages", [])
    )

    if render_failed:
        status = "failure"
    elif pipeline.get("partial"):
        status = "partial"
    else:
        status = "success"

    # ---- Local-model executive synthesis (apply only; dry-run keeps the deterministic preview) ----
    # The synthesized narrative becomes the primary brief; the deterministic candidates become a
    # collapsed source-linked audit appendix (hybrid). Fail-closed: a degraded/unavailable/low-quality
    # model run never produces a full "success". But the banner + final status are DEFERRED to the
    # post-usefulness-gate finalization, because a deterministic-useful brief with degraded synthesis
    # is a publishable operator fallback (`deterministic_success_synthesis_degraded`), NOT the same
    # class as an unusable brief. The deterministic markdown is kept here for that decision.
    synthesis_meta: Optional[dict[str, Any]] = None
    synthesis_dump: Optional[dict[str, Any]] = None
    synthesis_degraded = False
    synth_degraded_reason: Optional[str] = None
    if synthesize_brief and not dry_run and status != "failure" and markdown:
        from .daily_brief_llm_synthesis import (
            render_synthesis_markdown,
            synthesize_daily_brief,
        )

        synth = synthesize_daily_brief(
            store=store,
            brief_date=brief_date,
            window=window,
            now_utc=pipeline_now,
            db_path=db_path,
            profile_id=synthesis_profile_id,
            backend=synthesis_backend,
            dry_run=False,
        )
        synthesis_meta = synth.metadata()
        if synth.degraded or synth.synthesis is None:
            synthesis_degraded = True
            synth_degraded_reason = synth.degraded_reason or synth.status
            # Keep `markdown` as the deterministic brief; the banner + status class are decided after
            # the usefulness gate (deterministic-fallback vs usefulness-failed).
            warnings.append(
                f"synthesis_degraded: {synth_degraded_reason}; "
                "deterministic fallback evaluated after usefulness gate"
            )
        else:
            synthesis_dump = synth.synthesis.model_dump(mode="json")
            markdown = (
                render_synthesis_markdown(
                    synth.synthesis,
                    brief_date=brief_date,
                    window=window,
                    model_metadata=synthesis_meta,
                    generated_label=now_utc,
                )
                + "\n\n---\n\n## Appendix: Source-Linked Candidates (audit)\n\n"
                + _render_md_appendix(sections)
            )

    # ---- Email raw enrichment apply stage (Candidate C) — bounded, capped, idempotent, source-linked ----
    # Runs only in apply mode when enabled; persists review-safe V45 rows so the converged Model
    # Enriched Intelligence section can consume them in the SAME run. Dry-run reports would_persist
    # but writes nothing. Fail-closed/advisory: never raises into the deterministic run.
    email_enrichment_receipt = _run_email_raw_enrichment_stage(
        store=store,
        now_utc=pipeline_now,
        enabled=email_raw_enrichment,
        dry_run=dry_run,
        max_persist=(
            email_raw_enrichment_max_persist
            if email_raw_enrichment_max_persist is not None
            else max_persist_per_stage
        ),
        backend=email_raw_enrichment_backend,
        present_models=email_raw_enrichment_present_models,
    )
    for w in email_enrichment_receipt.get("warnings", []):
        if w not in warnings:
            warnings.append(w)

    # ---- Converged Model Enriched Intelligence section (default-on, deterministic + advisory) ----
    # ONE operator-facing section: source-linked advisory bullets (the intelligence adapter) + the
    # raw-free V45 pending follow-up rows (including any persisted by the stage above). Default-on;
    # explicit disable via model_enriched_intelligence=False. Withheld/degraded → honest banner +
    # deterministic brief preserved; pending rows still surface. Never raw; never accepted fact.
    from ..daily_brief.email_followup_pending import (
        build_pending_email_enrichment_section,
        render_pending_enrichment_markdown,
    )
    from .model_enriched_intelligence import (
        build_model_enriched_intelligence,
        render_model_enriched_markdown,
        status_block,
    )

    try:
        pending_followup = build_pending_email_enrichment_section(store)
    except Exception as exc:  # advisory only — never fail the deterministic run
        pending_followup = {
            "section": "email_followup_pending_enrichment",
            "available": False,
            "degraded_reason": f"enrichment_error:{str(exc)[:80]}",
            "count": 0,
            "items": [],
        }

    # Build the unified status object always (so status reports the posture). When disabled the
    # builder returns a cheap envelope WITHOUT calling the model; pending rows still surface.
    model_enriched = build_model_enriched_intelligence(
        store=store,
        brief_date=brief_date,
        enabled=model_enriched_intelligence,
        dry_run=dry_run,
        generation_mode="pipeline_apply" if not dry_run else "pipeline_dry_run",
        backend=model_enriched_backend,
        present_models=model_enriched_present_models,
        pending_section=pending_followup,
        generated_utc=now_utc,
    )
    # When executive synthesis degraded, present the model-enriched section as WITHHELD (deterministic
    # fallback) — never as available/healthy while the brief says synthesis degraded. The advisory
    # model bullets are withheld; the raw-free pending rows still surface under a non-model label.
    if synthesis_degraded and model_enriched.get("available"):
        model_enriched["available"] = False
        model_enriched["degraded"] = True
        model_enriched["withheld_reason"] = f"synthesis_degraded:{synth_degraded_reason}"
        model_enriched["label"] = "Source-Linked Deterministic Brief"
    mei_status = status_block(model_enriched)
    if model_enriched_intelligence:
        # Default-on path: ONE converged "Model Enriched Intelligence" section (advisory + pending).
        mei_render = model_enriched
        mei_md = render_model_enriched_markdown(model_enriched)
        if mei_md:
            markdown = (markdown + "\n\n---\n\n" + mei_md) if markdown else mei_md
    else:
        # Disabled: no MEI section; the legacy standalone pending card/markdown still surfaces.
        mei_render = None
        pending_md = (
            render_pending_enrichment_markdown(pending_followup)
            if pending_followup.get("available")
            else ""
        )
        if pending_md:
            markdown = (markdown + "\n\n---\n\n" + pending_md) if markdown else pending_md

    pending_summary = {
        "section": pending_followup.get("section"),
        "available": bool(pending_followup.get("available")),
        "count": int(pending_followup.get("count") or 0),
        "omitted_low_confidence": int(pending_followup.get("omitted_low_confidence") or 0),
        "dropped_leak": int(pending_followup.get("dropped_leak") or 0),
        "degraded_reason": pending_followup.get("degraded_reason"),
    }

    # ---- Usefulness gate (after deterministic projection + synthesis; before success is final) ----
    # Fail-closed: a run may stay "success" only if it meets the usefulness bar (>=1 useful
    # deterministic section, no source/deterministic contradiction, 100% executive source-ref
    # coverage, project-like calendar not all unresolved, Procore top rows not aggregate sludge).
    # Otherwise downgrade to "partial" so the last-successful pointer + latest.html are preserved and
    # the status explains usefulness_gate_failed.
    from .usefulness_gate import evaluate_usefulness_gate

    usefulness = evaluate_usefulness_gate(
        store=store,
        brief_date=brief_date,
        synthesis_present=synthesis_dump is not None,
        synthesis_degraded=synthesis_degraded,
    )
    # ---- Finalize the run result class (after usefulness gate) ----
    # Only an apply-mode run persists candidates and runs synthesis, so result-class refinement applies
    # to an apply-mode base "success" (a dry-run "success" is a preview, left unchanged). Distinguish:
    #   - usefulness gate FAILED → "degraded" (deterministic output unusable; render the not-successful
    #     degraded banner; last-successful + stable latest paths preserved);
    #   - usefulness PASSED + synthesis degraded → "deterministic_success_synthesis_degraded"
    #     (operator-usable deterministic fallback; render the operator-usable banner; publish the
    #     separate deterministic-latest path; daily-brief-latest.html reserved for full success);
    #   - usefulness PASSED + synthesis ok → "success".
    deterministic_fallback_used = False
    if status == "success" and not dry_run:
        if not usefulness.passed:
            status = "degraded"
            warnings.append("usefulness_gate_failed: " + ",".join(usefulness.failed_reasons))
            if synthesis_degraded:
                from .daily_brief_llm_synthesis import render_degraded_markdown

                markdown = render_degraded_markdown(
                    brief_date=brief_date,
                    window=window,
                    model_metadata=synthesis_meta or {},
                    generated_label=now_utc,
                    deterministic_markdown=markdown,
                )
        elif synthesis_degraded:
            status = STATUS_DETERMINISTIC_FALLBACK
            deterministic_fallback_used = True
            from .daily_brief_llm_synthesis import render_deterministic_fallback_markdown

            markdown = render_deterministic_fallback_markdown(
                brief_date=brief_date,
                window=window,
                model_metadata=synthesis_meta or {},
                generated_label=now_utc,
                deterministic_markdown=markdown,
            )

    is_fresh_success = (
        status == "success" and not dry_run and pipeline.get("brief_freshness") == "fresh"
    )
    published_deterministic = False

    outputs: dict[str, str] = {"vault_brief_dir_redacted": vault_brief_dir_redacted}
    egress_clean = True
    egress_matched: list[str] = []

    # Browser HTML (private local consumption). Skip on dry-run and on failure.
    if generate_browser and not dry_run and status != "failure" and markdown:
        rendered = render_daily_run_html(
            brief_date=brief_date,
            status=status,
            sections=sections,
            summary=summary,
            warnings=warnings,
            generated_label=now_utc,
            date_policy=window.to_dict(),
            extra_section_label=window.carryover_section_label,
            synthesis=synthesis_dump,
            model_metadata=synthesis_meta,
            degraded=synthesis_degraded,
            deterministic_fallback=deterministic_fallback_used,
            pending_followup=pending_followup,
            model_enriched=mei_render,
        )
        egress_matched = scan_daily_run_html(rendered)
        egress_clean = not egress_matched
        if egress_clean:
            dated = browser_dir / f"daily-brief-{brief_date}.html"
            _atomic_write(dated, rendered)
            _atomic_write(browser_dir / _BROWSER_ATTEMPTED, rendered)
            outputs["browser_dated_path"] = _redact_path(dated)
            outputs["browser_attempted_path"] = _redact_path(browser_dir / _BROWSER_ATTEMPTED)
            # Stable deterministic-latest path = the latest operator-usable brief (full success OR
            # deterministic fallback). daily-brief-latest.html stays reserved for full synthesis success.
            if is_fresh_success or deterministic_fallback_used:
                _atomic_write(browser_dir / _BROWSER_LATEST_DETERMINISTIC, rendered)
                outputs["browser_latest_deterministic_path"] = _redact_path(
                    browser_dir / _BROWSER_LATEST_DETERMINISTIC
                )
                published_deterministic = True
            if is_fresh_success:
                _atomic_write(browser_dir / _BROWSER_LATEST, rendered)
                outputs["browser_latest_path"] = _redact_path(browser_dir / _BROWSER_LATEST)
        else:
            warnings.append(
                "browser_egress_blocked: external-asset pattern detected; HTML withheld"
            )
            status = (
                "failure"
                if status in ("success", STATUS_DETERMINISTIC_FALLBACK)
                else status
            )
            deterministic_fallback_used = False

    # Governed Obsidian note (raw allowed). Requires explicit confirmation; skip on dry-run/failure.
    if write_obsidian and not dry_run and status != "failure" and markdown:
        if not confirm_vault_write:
            warnings.append("vault_write_requires_confirmation: Obsidian note not written")
        else:
            from ..daily_brief.output import write_brief_output

            content = markdown
            # The synthesized/degraded markdown already carries the carryover label in its heading;
            # only the plain deterministic markdown (synthesis disabled) needs the callout prepended.
            if window.carryover_section_label and synthesis_meta is None:
                content = f"> **{window.carryover_section_label}**\n\n{markdown}"
            res = write_brief_output(
                brief_date=brief_date, content=content, vault_brief_dir=vault_brief_dir, apply=True
            )
            outputs["obsidian_path_redacted"] = res.output_path_redacted or ""

    # Stable latest-successful browser path (preserved across failures).
    last_good = _read_last_successful_browser(status_d)
    if last_good:
        outputs["last_successful_path"] = last_good

    failure_reason = None
    if status == "failure":
        failure_reason = "render_stage_failed" if render_failed else "browser_egress_blocked"

    # ---- Deterministic-fallback / operator-usability block (status JSON + payload) ----
    # A deterministic-useful brief with degraded synthesis is reported as an explicit, published
    # fallback — distinct from a usefulness-gate failure. `operator_usable` is true whenever the
    # usefulness gate passed and the run did not hard-fail (regardless of synthesis health).
    synthesis_status = (
        None if synthesis_meta is None else ("degraded" if synthesis_degraded else "ok")
    )
    _ug_metrics = usefulness.metrics or {}
    _sec_counts = _ug_metrics.get("section_counts") or {}
    deterministic_fallback = {
        "used": deterministic_fallback_used,
        "reason": (f"synthesis_degraded:{synth_degraded_reason}" if synthesis_degraded else None),
        "usefulness_gate_passed": bool(usefulness.passed),
        "published": bool(published_deterministic),
        "stable_path": outputs.get("browser_latest_deterministic_path"),
        "counts": {
            "total_candidates": int(_ug_metrics.get("total_candidates") or 0),
            "calendar": int(_sec_counts.get("calendar") or 0),
            "procore": int(_sec_counts.get("procore") or 0),
        },
    }
    operator_usable = bool(usefulness.passed and status != "failure")

    # Operator-legible run summary — one consolidated, redacted block surfacing result, wall-clock
    # started/completed, the final output paths (browser / Obsidian / last-successful), partial stage
    # receipts (name+status only), and a safe error summary. No raw content.
    run_summary = _build_run_summary(
        status=status,
        degraded=synthesis_degraded,
        deterministic_fallback=deterministic_fallback_used,
        started_wall_utc=started_wall_utc,
        completed_wall_utc=datetime.now(_dt_tz.utc).isoformat(),
        brief_date=brief_date,
        brief_freshness=pipeline.get("brief_freshness"),
        outputs=outputs,
        stages=_redacted_stages(pipeline),
        failure_reason=failure_reason,
        warnings=warnings,
        pending_count=int(pending_summary.get("count") or 0),
        model_enriched=mei_status,
    )

    status_path = _write_status(
        status_d,
        now_utc,
        status=status,
        window=window,
        pipeline=pipeline,
        outputs=outputs,
        warnings=warnings,
        failure_reason=failure_reason,
        is_success=is_fresh_success,
        synthesis=synthesis_meta,
        pending_followup=pending_summary,
        model_enriched_intelligence=mei_status,
        email_raw_enrichment_stage=email_enrichment_receipt,
        run_summary=run_summary,
        usefulness_gate=usefulness.to_dict(),
        deterministic_fallback=deterministic_fallback,
        synthesis_status=synthesis_status,
        operator_usable=operator_usable,
    )
    outputs["status_path"] = _redact_path(status_path)

    return {
        "command": cmd,
        "ok": status != "failure",
        "status": status,
        # `partial` now tracks the top-level status exactly (no more status=partial / partial=false).
        "partial": status == "partial",
        "dry_run": dry_run,
        "brief_date": brief_date,
        "brief_freshness": pipeline.get("brief_freshness"),
        "date_policy": window.to_dict(),
        "summary": pipeline.get("summary"),
        "stages": _redacted_stages(pipeline),
        "warnings": warnings,
        "outputs": outputs,
        "synthesis": synthesis_meta,
        "synthesis_degraded": synthesis_degraded,
        "synthesis_status": synthesis_status,
        "synthesis_required_for_success": False,
        "deterministic_fallback": deterministic_fallback,
        "deterministic_fallback_used": deterministic_fallback_used,
        "operator_usable": operator_usable,
        "pending_followup": pending_summary,
        "model_enriched_intelligence": mei_status,
        "email_raw_enrichment_stage": email_enrichment_receipt,
        "run_summary": run_summary,
        "usefulness_gate": usefulness.to_dict(),
        "egress_scan": {"clean": egress_clean, "matched_labels": egress_matched},
        "failure_reason": failure_reason,
        "guardrails": _guardrails(include_raw, dry_run, generate_browser),
    }


def _guardrails(include_raw: bool, dry_run: bool, generate_browser: bool) -> dict[str, Any]:
    return {
        "dry_run_default": True,
        "weekday_aware_policy": True,
        "raw_local_consumption_only": include_raw,
        "browser_outside_repo": True,
        "no_browser_auto_open": True,
        "governed_vault_write_requires_confirmation": True,
        "vault_brief_folder_pinned": True,
        "legacy_phase_08a_folder_guarded": True,
        "redacted_status_file": True,
        "preserves_last_successful_brief": True,
        "no_external_writeback": True,
        "advisory_only": True,
    }


def _redacted_stages(pipeline: dict[str, Any]) -> list[dict[str, Any]]:
    """Stage receipts with counts only — drop the verbose detail block (safe for status file)."""
    return [{k: v for k, v in s.items() if k != "detail"} for s in pipeline.get("stages", [])]


def _build_run_summary(
    *,
    status: str,
    degraded: bool,
    deterministic_fallback: bool = False,
    started_wall_utc: str,
    completed_wall_utc: str,
    brief_date: str,
    brief_freshness: Any,
    outputs: dict[str, str],
    stages: list[dict[str, Any]],
    failure_reason: Optional[str],
    warnings: list[str],
    pending_count: int,
    model_enriched: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """One operator-legible, redacted run summary (no raw content; paths already ``~/…`` redacted).

    ``result`` reports degraded explicitly (a degraded synthesis is a partial run that is NOT counted
    as a fresh success, so the last-successful pointer is preserved). ``stage_receipts`` are name +
    status only. ``error_summary`` prefers the structured failure reason, else the last warning on a
    non-success run, else None.
    """
    if deterministic_fallback:
        result = STATUS_DETERMINISTIC_FALLBACK
    elif degraded and status != "failure":
        result = "degraded"
    else:
        result = status
    error_summary = failure_reason
    if error_summary is None and status not in ("success", STATUS_DETERMINISTIC_FALLBACK) and warnings:
        error_summary = warnings[-1][:160]
    return {
        "result": result,
        "raw_status": status,
        "degraded": bool(degraded),
        "started_utc": started_wall_utc,
        "completed_utc": completed_wall_utc,
        "brief_date": brief_date,
        "brief_freshness": brief_freshness,
        "browser_output_path": outputs.get("browser_latest_path")
        or outputs.get("browser_dated_path"),
        "obsidian_output_path": outputs.get("obsidian_path_redacted") or None,
        "last_successful_path": outputs.get("last_successful_path"),
        "stage_receipts": [
            {"stage": s.get("stage"), "status": s.get("status")} for s in stages
        ],
        "error_summary": error_summary,
        "pending_followup_count": pending_count,
        "model_enriched_intelligence": {
            "enabled": bool((model_enriched or {}).get("enabled")),
            "available": bool((model_enriched or {}).get("available")),
            "degraded": bool((model_enriched or {}).get("degraded")),
            "withheld_reason": (model_enriched or {}).get("withheld_reason"),
            "label": (model_enriched or {}).get("label") or "Model Enriched Intelligence",
            "source_linked_bullets": int((model_enriched or {}).get("bullets_kept") or 0),
            "pending_followup_count": int(
                (model_enriched or {}).get("pending_followup_count") or 0
            ),
        },
        "browser_auto_opened": False,
    }


def _read_last_successful_browser(status_dir: Path) -> Optional[str]:
    try:
        data = json.loads((status_dir / _LAST_SUCCESSFUL).read_text(encoding="utf-8"))
        return data.get("browser_latest_path")
    except Exception:
        return None


def _failure_receipt(cmd: str, reason: str, *, detail: str) -> dict[str, Any]:
    return {
        "command": cmd,
        "ok": False,
        "status": "failure",
        "partial": False,
        "error": reason,
        "detail": detail,
        "outputs": {},
        "egress_scan": {"clean": True, "matched_labels": []},
        "guardrails": {"browser_outside_repo": True},
    }


def _write_status(
    status_dir: Path,
    now_utc: str,
    *,
    status: str,
    window: DailyBriefWindow,
    pipeline: Optional[dict[str, Any]],
    outputs: dict[str, str],
    warnings: list[str],
    failure_reason: Optional[str],
    is_success: bool,
    synthesis: Optional[dict[str, Any]] = None,
    pending_followup: Optional[dict[str, Any]] = None,
    model_enriched_intelligence: Optional[dict[str, Any]] = None,
    email_raw_enrichment_stage: Optional[dict[str, Any]] = None,
    run_summary: Optional[dict[str, Any]] = None,
    usefulness_gate: Optional[dict[str, Any]] = None,
    deterministic_fallback: Optional[dict[str, Any]] = None,
    synthesis_status: Optional[str] = None,
    operator_usable: bool = False,
) -> Path:
    """Write the redacted machine-readable status (latest + dated). Never contains raw bodies.

    ``synthesis`` carries only safe model metadata (profile/model/status/latency/degraded) — never a
    raw prompt or response. ``pending_followup`` carries only counts/labels (section name, available,
    count, omitted/dropped counters) — never row-level enrichment content."""
    payload: dict[str, Any] = {
        "command": "second-brain daily-run run",
        "run_timestamp": now_utc,
        "git_head": _git_head_short(),
        "status": status,
        "run_summary": run_summary,
        "brief_date": window.run_date,
        "brief_freshness": pipeline.get("brief_freshness") if pipeline else "skipped",
        "date_policy": window.to_dict(),
        "stages": _redacted_stages(pipeline) if pipeline else [],
        "summary": pipeline.get("summary") if pipeline else {},
        "outputs": outputs,
        "synthesis": synthesis,
        "pending_followup": pending_followup,
        "model_enriched_intelligence": model_enriched_intelligence,
        "email_raw_enrichment_stage": email_raw_enrichment_stage,
        "usefulness_gate": usefulness_gate,
        "synthesis_status": synthesis_status,
        "synthesis_required_for_success": False,
        "deterministic_fallback": deterministic_fallback,
        "operator_usable": operator_usable,
        "warnings": warnings,
        "failure_reason": failure_reason,
    }
    blob = json.dumps(payload, indent=2, default=str)
    latest = status_dir / _LATEST_STATUS
    _atomic_write(latest, blob)
    _atomic_write(status_dir / f"status-{_stamp(now_utc)}.json", blob)

    # Update the last-successful pointer ONLY on a fresh success (preserves last-good on failure).
    if is_success:
        pointer = {
            "brief_date": window.run_date,
            "updated": now_utc,
            "browser_latest_path": outputs.get("browser_latest_path"),
            "obsidian_path_redacted": outputs.get("obsidian_path_redacted"),
        }
        _atomic_write(status_dir / _LAST_SUCCESSFUL, json.dumps(pointer, indent=2, default=str))
    return latest
