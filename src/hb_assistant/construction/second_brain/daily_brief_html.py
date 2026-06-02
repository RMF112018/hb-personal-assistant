"""Phase 08B Local HTML Brief Renderer (Prompt 10).

Renders a polished, responsive, **fully self-contained** interactive HTML daily-brief page from the
durable V27 delivery handoff (`read_daily_brief_handoff` -> `DeliveryHandoffPayload`) and writes it
to a safe path **outside the repo and the vault** (`<app_support>/html/`). The page uses inline
CSS/JS only — NO external assets and NO network calls — and is rendered from the structured,
redacted handoff (titles + source-ref pairs), never from a model response.

Interactive UI: project + tier filters, collapsible sections, a slide-out evidence drawer, a warning
banner, a meeting timeline, a mandatory-review panel, and print CSS.

Guardrails: the agent runs a fail-closed external-asset / network scan before writing (refuses on any
hit -> ``HTML_RENDER_EXTERNAL_ASSET_BLOCKED``); the V32 ``daily_brief_html_render_receipts`` row is
metadata-only (redacted path + content/path hashes), enforces ``no_external_assets = 1`` at the DB
layer, and the raw HTML is NEVER persisted in SQLite. Dry-run is the default; the V28 agent receipt
is emit-gated. No external writeback/delivery.

Reason codes: ``HTML_RENDER_NEVER_GENERATED`` (no brief for the date), ``HTML_RENDER_BLOCKED`` (run
blocked/degraded), ``HTML_RENDER_STALE`` (older than ``max_age_hours``), ``HTML_RENDER_ELIGIBLE``
(ready; dry-run preview), ``HTML_RENDER_COMPLETED`` (apply wrote the HTML + receipt),
``HTML_RENDER_ALREADY_RENDERED`` (idempotent no-op), ``HTML_RENDER_EXTERNAL_ASSET_BLOCKED``
(fail-closed: the rendered HTML referenced an external asset / network call).
"""

from __future__ import annotations

import hashlib
import html
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.connection import get_connection, transaction
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

from .automation_policy import load_phase_08b_automation_policy_seed
from .daily_brief.models import HANDOFF_SECTIONS
from .daily_brief.output import _atomic_write_text
from .daily_brief.store import read_daily_brief_handoff, read_latest_daily_brief_runs

_FORBIDDEN_TOKENS = (
    "raw_body",
    "raw_document_text",
    "raw_calendar_payload",
    "raw_prompt",
    "raw_response",
    "signed_url",
    "download_url",
    "secret",
    "token",
)

# Reason codes (declared in the Phase 08B automation policy + gate contracts).
HTML_RENDER_NEVER_GENERATED = "HTML_RENDER_NEVER_GENERATED"
HTML_RENDER_BLOCKED = "HTML_RENDER_BLOCKED"
HTML_RENDER_STALE = "HTML_RENDER_STALE"
HTML_RENDER_ELIGIBLE = "HTML_RENDER_ELIGIBLE"
HTML_RENDER_COMPLETED = "HTML_RENDER_COMPLETED"
HTML_RENDER_ALREADY_RENDERED = "HTML_RENDER_ALREADY_RENDERED"
HTML_RENDER_EXTERNAL_ASSET_BLOCKED = "HTML_RENDER_EXTERNAL_ASSET_BLOCKED"

_DEFAULT_MAX_AGE_HOURS = 36
_BLOCKED_STATUS = "blocked"

# Human-facing section headings (HANDOFF_SECTIONS order).
_SECTION_HEADINGS: dict[str, str] = {
    "priority_actions": "Priority Actions",
    "waiting_on": "Waiting On / Warnings",
    "meeting_prep": "Meeting Prep",
    "file_review_queue": "File Review Queue (mandatory review)",
    "project_signals": "Project Signals",
}

# Value-shaped external-asset / network patterns. Designed NOT to match this module's own clean,
# fully-inline markup (no http, no src=, no url(//, no fetch(, no //-comments).
_EXTERNAL_ASSET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"""=\s*["']\s*//"""),  # protocol-relative attribute value
    re.compile(r"<link\b", re.IGNORECASE),
    re.compile(r"<script[^>]*\bsrc\s*=", re.IGNORECASE),
    re.compile(r"<img[^>]*\bsrc\s*=", re.IGNORECASE),
    re.compile(r"<iframe\b", re.IGNORECASE),
    re.compile(r"@import\b", re.IGNORECASE),
    re.compile(r"url\(\s*['\"]?\s*(?:https?:)?//", re.IGNORECASE),
    re.compile(r"\bfetch\s*\(", re.IGNORECASE),
    re.compile(r"\bXMLHttpRequest\b"),
    re.compile(r"\bWebSocket\b"),
    re.compile(r"\.sendBeacon\b"),
    re.compile(r"\bimport\s*\("),
)


def _scan_html_for_external_assets(rendered_html: str) -> list[str]:
    """Return external-asset / network pattern labels present in ``rendered_html`` (empty = clean)."""
    return [p.pattern for p in _EXTERNAL_ASSET_PATTERNS if p.search(rendered_html)]


class DailyBriefHtmlRenderStatus(BaseModel):
    """Daily-brief HTML render snapshot (metadata-only; redacted; no raw content / no raw HTML)."""

    overall_status: str  # "ok" | "attention"
    reason_code: str
    brief_date: str | None = None
    brief_run_id: str | None = None
    eligible: bool = False
    already_rendered: bool = False
    mode: str | None = None  # "dry_run" | "apply"
    render_status: str | None = None  # "preview" | "rendered" | "already_rendered" | "skipped"
    written: bool = False
    no_external_assets: bool = True
    external_asset_findings: int = 0
    content_hash: str | None = None
    html_path_redacted: str | None = None
    html_path_hash: str | None = None
    rendered_utc: str | None = None
    last_run_status: str | None = None
    degradation_mode: str | None = None
    age_seconds: int | None = None
    runs_examined: int = 0
    policy_version: str = "unknown"
    schema_version: int = 0
    schema_expected: int = LATEST_SCHEMA_VERSION
    generated_utc: str = ""
    detail: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("detail", "degradation_mode", "html_path_redacted")
    @classmethod
    def _no_forbidden_tokens(cls, value: str | None) -> str | None:
        if value and any(t in value for t in _FORBIDDEN_TOKENS):
            raise ValueError("daily-brief-html field must not carry raw/forbidden tokens")
        return value


def _resolved_db(db_path: str | None) -> str:
    return db_path if db_path is not None else str(PathPolicy().get_db_path())


def _safe_seed() -> dict[str, Any]:
    try:
        seed = load_phase_08b_automation_policy_seed()
    except Exception:  # pragma: no cover - defensive
        return {}
    return seed if isinstance(seed, dict) else {}


def _cfg() -> dict[str, Any]:
    cfg = _safe_seed().get("daily_brief_html_render", {})
    return cfg if isinstance(cfg, dict) else {}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        text = value.replace("Z", "+00:00") if value.endswith("Z") else value
        dt = datetime.fromisoformat(text)
    except (ValueError, AttributeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _values_only_blob(obj: Any) -> str:
    """Concatenate VALUES (not dict keys) so the raw-content scan ignores schema field names."""
    out: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v)
        elif node is not None:
            out.append(str(node))

    walk(obj)
    return " ".join(out)


def _select_run(runs: list[dict[str, Any]], brief_date: str | None) -> dict[str, Any] | None:
    if brief_date is not None:
        for run in runs:
            if str(run.get("brief_date")) == brief_date:
                return run
        return None
    return runs[0] if runs else None


def _prior_rendered(brief_run_id: str | None, brief_date: str | None, db_path: str | None) -> bool:
    """True when a V32 receipt already records a completed render for this brief."""
    SQLiteMigrator(db_path).apply()
    conn = get_connection(Path(db_path) if db_path is not None else None)
    if brief_run_id is not None:
        row = conn.execute(
            "SELECT COUNT(*) FROM daily_brief_html_render_receipts "
            "WHERE render_status = 'rendered' AND brief_run_id = ?",
            (brief_run_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) FROM daily_brief_html_render_receipts "
            "WHERE render_status = 'rendered' AND brief_date = ?",
            (brief_date,),
        ).fetchone()
    return bool(row and row[0])


def write_daily_brief_html_render_receipt(
    *,
    brief_date: str,
    render_status: str,
    reason_code: str,
    mode: str,
    brief_run_id: str | None = None,
    content_hash: str | None = None,
    html_path_redacted: str | None = None,
    html_path_hash: str | None = None,
    rendered_utc: str | None = None,
    db_path: str | None = None,
) -> str:
    """Insert one metadata-only V32 render receipt; returns ``html_render_receipt_id``.

    Local-only, additive. Raw HTML is never stored; ``no_external_assets`` stays 1 (DB CHECK) and the
    no-raw / no-writeback guard columns stay at 0 via DB CHECKs.
    """
    SQLiteMigrator(db_path).apply()  # ensure V32 table exists (idempotent)
    receipt_id = uuid.uuid4().hex
    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO daily_brief_html_render_receipts
                (html_render_receipt_id, brief_run_id, brief_date, render_status, reason_code, mode,
                 content_hash, html_path_redacted, html_path_hash, rendered_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_id,
                brief_run_id,
                brief_date,
                render_status,
                reason_code,
                mode,
                content_hash,
                html_path_redacted,
                html_path_hash,
                rendered_utc,
            ),
        )
    return receipt_id


# --- HTML rendering (pure, deterministic, fully self-contained) -------------------------------

_CSS = """
:root{--bg:#0f172a;--panel:#1e293b;--card:#273449;--ink:#e2e8f0;--muted:#94a3b8;
--accent:#38bdf8;--warn:#f59e0b;--danger:#ef4444;--ok:#22c55e;--line:#334155;}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
background:var(--bg);color:var(--ink);line-height:1.5}
header.brief-head{padding:24px 28px;border-bottom:1px solid var(--line);position:sticky;top:0;
background:linear-gradient(180deg,#0f172a,#101b30);z-index:5}
header.brief-head h1{margin:0 0 4px;font-size:22px}
header.brief-head .meta{color:var(--muted);font-size:13px}
.banner{margin:16px 28px;padding:12px 16px;border-radius:10px;font-size:14px;border:1px solid}
.banner.warn{background:rgba(245,158,11,.12);border-color:var(--warn);color:#fde68a}
.banner.danger{background:rgba(239,68,68,.12);border-color:var(--danger);color:#fecaca}
.controls{display:flex;flex-wrap:wrap;gap:18px;padding:16px 28px;border-bottom:1px solid var(--line)}
.filter-group{display:flex;flex-direction:column;gap:6px}
.filter-group .label{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{cursor:pointer;border:1px solid var(--line);background:var(--card);color:var(--ink);
padding:5px 12px;border-radius:999px;font-size:12px;user-select:none}
.chip.active{background:var(--accent);color:#06283d;border-color:var(--accent);font-weight:600}
main{padding:8px 28px 64px;max-width:1024px}
section.brief-section{margin:18px 0;border:1px solid var(--line);border-radius:12px;overflow:hidden;
background:var(--panel)}
.sec-head{display:flex;align-items:center;gap:10px;cursor:pointer;padding:14px 18px;
background:var(--card);user-select:none}
.sec-head .caret{transition:transform .15s ease;color:var(--accent)}
section.brief-section.collapsed .caret{transform:rotate(-90deg)}
section.brief-section.collapsed .sec-body{display:none}
.sec-head h2{margin:0;font-size:15px;flex:1}
.count{font-size:12px;color:var(--muted);background:#0b1424;border:1px solid var(--line);
border-radius:999px;padding:2px 9px}
.sec-body{padding:10px 18px 16px}
.brief-item{display:flex;align-items:flex-start;gap:10px;padding:10px 12px;border-radius:9px;
border:1px solid transparent}
.brief-item:hover{border-color:var(--line);background:#1a2740}
.brief-item.hidden{display:none}
.tier{flex:none;font-size:11px;font-weight:700;border-radius:6px;padding:2px 7px;margin-top:2px}
.tier.t1{background:rgba(34,197,94,.18);color:#86efac}
.tier.t2{background:rgba(56,189,248,.18);color:#7dd3fc}
.tier.t3{background:rgba(239,68,68,.18);color:#fca5a5}
.item-main{flex:1}
.item-title{font-size:14px}
.item-sub{font-size:12px;color:var(--muted);margin-top:2px}
.ev-btn{flex:none;cursor:pointer;font-size:11px;border:1px solid var(--line);background:#0b1424;
color:var(--accent);border-radius:7px;padding:4px 9px}
.timeline .brief-item{position:relative;border-left:2px solid var(--line);margin-left:8px;
padding-left:20px}
.timeline .brief-item::before{content:'';position:absolute;left:-7px;top:14px;width:10px;height:10px;
border-radius:50%;background:var(--accent)}
section.review-panel{border-color:var(--danger)}
section.review-panel .sec-head{background:rgba(239,68,68,.10)}
.empty{color:var(--muted);font-style:italic;padding:8px 12px}
#evidence-drawer{position:fixed;top:0;right:0;height:100%;width:360px;max-width:88vw;
background:#0b1424;border-left:1px solid var(--line);transform:translateX(100%);
transition:transform .2s ease;z-index:20;display:flex;flex-direction:column}
#evidence-drawer.open{transform:translateX(0)}
#evidence-drawer .drawer-head{display:flex;align-items:center;justify-content:space-between;
padding:16px 18px;border-bottom:1px solid var(--line)}
#evidence-drawer h3{margin:0;font-size:14px}
#evidence-drawer .close{cursor:pointer;border:none;background:none;color:var(--muted);font-size:20px}
#evidence-drawer .drawer-body{padding:16px 18px;overflow:auto}
#evidence-drawer .ref{font-size:12px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;
margin-bottom:8px;word-break:break-word}
#drawer-scrim{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:15;display:none}
#drawer-scrim.open{display:block}
footer.brief-foot{padding:18px 28px;color:var(--muted);font-size:12px;border-top:1px solid var(--line)}
@media (max-width:640px){.controls{gap:12px}main{padding:8px 16px 48px}header.brief-head{padding:18px}}
@media print{.controls,.ev-btn,#evidence-drawer,#drawer-scrim,header.brief-head{position:static}
.controls,.ev-btn,#evidence-drawer,#drawer-scrim{display:none!important}
body{background:#fff;color:#000}section.brief-section,.sec-head{background:#fff;border-color:#bbb}
section.brief-section.collapsed .sec-body{display:block!important}.brief-item.hidden{display:flex!important}
.tier{border:1px solid #999}}
"""

_JS = """
(function(){
  var tierSel='all',projSel='all';
  function apply(){
    var items=document.querySelectorAll('.brief-item');
    for(var i=0;i<items.length;i++){
      var it=items[i];
      var okTier=(tierSel==='all')||(it.getAttribute('data-tier')===tierSel);
      var p=it.getAttribute('data-project');
      var okProj=(projSel==='all')||(p===projSel);
      if(okTier&&okProj){it.classList.remove('hidden');}else{it.classList.add('hidden');}
    }
    var secs=document.querySelectorAll('section.brief-section');
    for(var s=0;s<secs.length;s++){
      var vis=secs[s].querySelectorAll('.brief-item:not(.hidden)').length;
      var c=secs[s].querySelector('.count');if(c){c.textContent=vis;}
    }
  }
  function bindChips(group,setter){
    var chips=document.querySelectorAll('[data-group="'+group+'"]');
    for(var i=0;i<chips.length;i++){
      chips[i].addEventListener('click',function(e){
        var g=e.currentTarget.getAttribute('data-group');
        var sel=document.querySelectorAll('[data-group="'+g+'"]');
        for(var k=0;k<sel.length;k++){sel[k].classList.remove('active');}
        e.currentTarget.classList.add('active');
        setter(e.currentTarget.getAttribute('data-value'));apply();
      });
    }
  }
  bindChips('tier',function(v){tierSel=v;});
  bindChips('project',function(v){projSel=v;});
  var heads=document.querySelectorAll('.sec-head');
  for(var h=0;h<heads.length;h++){
    heads[h].addEventListener('click',function(e){
      e.currentTarget.parentNode.classList.toggle('collapsed');
    });
  }
  var drawer=document.getElementById('evidence-drawer');
  var scrim=document.getElementById('drawer-scrim');
  var body=document.getElementById('drawer-body');
  function closeDrawer(){drawer.classList.remove('open');scrim.classList.remove('open');}
  var evb=document.querySelectorAll('.ev-btn');
  for(var b=0;b<evb.length;b++){
    evb[b].addEventListener('click',function(e){
      e.stopPropagation();
      var refs=(e.currentTarget.getAttribute('data-refs')||'').split('|');
      var title=e.currentTarget.getAttribute('data-title')||'Evidence';
      var dt=document.getElementById('drawer-title');if(dt){dt.textContent=title;}
      body.innerHTML='';
      for(var r=0;r<refs.length;r++){
        var t=refs[r].trim();if(!t){continue;}
        var d=document.createElement('div');d.className='ref';d.textContent=t;body.appendChild(d);
      }
      if(!body.children.length){var n=document.createElement('div');n.className='ref';
        n.textContent='No source references recorded.';body.appendChild(n);}
      drawer.classList.add('open');scrim.classList.add('open');
    });
  }
  var cl=document.getElementById('drawer-close');if(cl){cl.addEventListener('click',closeDrawer);}
  scrim.addEventListener('click',closeDrawer);
})();
"""


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _project_key_from_title(title: str) -> str | None:
    m = re.match(r"^project\s+(\S+?):", title)
    return m.group(1) if m else None


def _render_item(line: Any) -> tuple[str, str]:
    """Render one ``.brief-item`` row; returns (html, data_project)."""
    tier = int(getattr(line, "review_tier", 3) or 3)
    title = getattr(line, "title_redacted", "")
    refs = getattr(line, "source_refs", []) or []
    project = _project_key_from_title(str(title)) or "_general"
    ref_pairs = [
        f"{r.get('source_family', '')}:{r.get('source_ref', '')}"
        for r in refs
        if (r.get("source_family") or r.get("source_ref"))
    ]
    sub = f"{len(ref_pairs)} source ref(s)" if ref_pairs else "no source refs"
    data_refs = _esc(" | ".join(ref_pairs))
    item = (
        f'<div class="brief-item" data-tier="{tier}" data-project="{_esc(project)}">'
        f'<span class="tier t{tier}">T{tier}</span>'
        f'<div class="item-main"><div class="item-title">{_esc(title)}</div>'
        f'<div class="item-sub">{_esc(sub)}</div></div>'
        f'<button class="ev-btn" data-title="{_esc(title)}" data-refs="{data_refs}">Evidence</button>'
        f"</div>"
    )
    return item, project


def render_daily_brief_html(payload: Any, *, generated_label: str) -> str:
    """Render a self-contained interactive HTML brief from a durable handoff payload (no raw content)."""
    brief_date = _esc(payload.brief_date)
    degradation = str(getattr(payload, "degradation_mode", "") or "")
    eligible = bool(getattr(payload, "eligible_for_delivery", False))
    review_tier = int(getattr(payload, "review_tier", 3) or 3)

    projects: list[str] = []
    section_html: list[str] = []
    for section in HANDOFF_SECTIONS:
        heading = _SECTION_HEADINGS.get(section, section.replace("_", " ").title())
        lines = payload.sections.get(section, [])
        rows: list[str] = []
        for line in lines:
            row, project = _render_item(line)
            rows.append(row)
            if project != "_general" and project not in projects:
                projects.append(project)
        body = "".join(rows) if rows else '<div class="empty">None.</div>'
        sec_classes = "brief-section"
        if section == "meeting_prep":
            sec_classes += " timeline-host"
        if section == "file_review_queue":
            sec_classes += " review-panel"
        body_classes = "sec-body timeline" if section == "meeting_prep" else "sec-body"
        section_html.append(
            f'<section class="{sec_classes}">'
            f'<div class="sec-head"><span class="caret">&#9662;</span>'
            f'<h2>{_esc(heading)}</h2><span class="count">{len(lines)}</span></div>'
            f'<div class="{body_classes}">{body}</div></section>'
        )

    # Warning banner (degradation / not eligible).
    banner = ""
    if not eligible or (degradation and degradation != "none"):
        cls = "danger" if (not eligible or degradation == "blocked") else "warn"
        msg = (
            "This brief is blocked or degraded and is routed to mandatory review — "
            "items are not presented as fact."
            if cls == "danger"
            else f"Degraded delivery (degradation={_esc(degradation)}); review recommended."
        )
        banner = f'<div class="banner {cls}">{msg}</div>'

    # Project filter chips (All + parsed projects + General).
    proj_chips = ['<span class="chip active" data-group="project" data-value="all">All</span>']
    for p in projects:
        proj_chips.append(
            f'<span class="chip" data-group="project" data-value="{_esc(p)}">{_esc(p)}</span>'
        )
    proj_chips.append(
        '<span class="chip" data-group="project" data-value="_general">General</span>'
    )
    tier_chips = [
        '<span class="chip active" data-group="tier" data-value="all">All</span>',
        '<span class="chip" data-group="tier" data-value="1">Tier 1</span>',
        '<span class="chip" data-group="tier" data-value="2">Tier 2</span>',
        '<span class="chip" data-group="tier" data-value="3">Tier 3</span>',
    ]

    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="referrer" content="no-referrer">',
        f"<title>Daily Brief {brief_date}</title>",
        f"<style>{_CSS}</style></head><body>",
        f'<header class="brief-head"><h1>Daily Brief &mdash; {brief_date}</h1>'
        f'<div class="meta">Local advisory brief &middot; review_tier={review_tier} &middot; '
        f"generated {_esc(generated_label)} &middot; self-contained (no network)</div></header>",
        banner,
        '<div class="controls">'
        f'<div class="filter-group"><span class="label">Project</span>'
        f'<div class="chips">{"".join(proj_chips)}</div></div>'
        f'<div class="filter-group"><span class="label">Tier</span>'
        f'<div class="chips">{"".join(tier_chips)}</div></div></div>',
        "<main>",
        *section_html,
        "</main>",
        '<footer class="brief-foot">Rendered locally from the redacted delivery handoff. '
        "No external assets, no network calls, no raw content.</footer>",
        '<div id="drawer-scrim"></div>',
        '<aside id="evidence-drawer"><div class="drawer-head">'
        '<h3 id="drawer-title">Evidence</h3>'
        '<button class="close" id="drawer-close">&times;</button></div>'
        '<div class="drawer-body" id="drawer-body"></div></aside>',
        f"<script>{_JS}</script>",
        "</body></html>",
    ]
    return "".join(parts)


# --- Agent (evaluate / run / proof) -----------------------------------------------------------


def evaluate_daily_brief_html_render(
    *, brief_date: str | None = None, db_path: str | None = None, now: datetime | None = None
) -> DailyBriefHtmlRenderStatus:
    """Read-only HTML-render eligibility for the latest (or ``brief_date``) brief. Writes nothing."""
    cfg = _cfg()
    max_age_seconds = int(cfg.get("max_age_hours", _DEFAULT_MAX_AGE_HOURS)) * 3600
    now = now or datetime.now(timezone.utc)
    seed = _safe_seed()
    try:
        schema_version = SQLiteMigrator(_resolved_db(db_path)).current_version()
    except Exception:  # pragma: no cover - defensive
        schema_version = 0
    generated = datetime.now(timezone.utc).isoformat()

    runs = read_latest_daily_brief_runs(db_path=db_path, limit=50)
    base: dict[str, Any] = {
        "policy_version": str(seed.get("version", "unknown")),
        "schema_version": schema_version,
        "generated_utc": generated,
        "runs_examined": len(runs),
    }

    run = _select_run(runs, brief_date)
    if run is None:
        return DailyBriefHtmlRenderStatus(
            overall_status="attention",
            reason_code=HTML_RENDER_NEVER_GENERATED,
            brief_date=brief_date,
            detail="no_daily_brief_run_for_date",
            **base,
        )

    run_brief_date = str(run.get("brief_date")) if run.get("brief_date") else None
    brief_run_id = str(run.get("brief_run_id")) if run.get("brief_run_id") else None
    last_status = str(run.get("status")) if run.get("status") is not None else None
    degradation = run.get("degradation_mode")
    last_utc = run.get("generated_utc")
    parsed = _parse_utc(str(last_utc) if last_utc else None)
    age = int((now.astimezone(timezone.utc) - parsed).total_seconds()) if parsed else None

    common: dict[str, Any] = {
        "brief_date": run_brief_date,
        "brief_run_id": brief_run_id,
        "last_run_status": last_status,
        "degradation_mode": str(degradation) if degradation else None,
        "age_seconds": age,
        **base,
    }

    if last_status == _BLOCKED_STATUS or str(degradation or "") == _BLOCKED_STATUS:
        return DailyBriefHtmlRenderStatus(
            overall_status="attention",
            reason_code=HTML_RENDER_BLOCKED,
            detail="brief_run_blocked_or_degraded",
            **common,
        )
    if age is not None and age > max_age_seconds:
        return DailyBriefHtmlRenderStatus(
            overall_status="attention",
            reason_code=HTML_RENDER_STALE,
            detail="brief_older_than_max_age",
            **common,
        )
    if _prior_rendered(brief_run_id, run_brief_date, db_path):
        return DailyBriefHtmlRenderStatus(
            overall_status="ok",
            reason_code=HTML_RENDER_ALREADY_RENDERED,
            eligible=True,
            already_rendered=True,
            detail="already_rendered_to_local_html",
            **common,
        )
    return DailyBriefHtmlRenderStatus(
        overall_status="ok",
        reason_code=HTML_RENDER_ELIGIBLE,
        eligible=True,
        detail="ready_for_local_html_render",
        **common,
    )


def run_daily_brief_html_render_agent(
    *,
    brief_date: str | None = None,
    mode: str = "dry_run",
    db_path: str | None = None,
    html_dir: str | None = None,
    now: datetime | None = None,
    emit_receipt: bool = False,
) -> tuple[DailyBriefHtmlRenderStatus, str | None]:
    """Evaluate, then (apply, dry-run default) render the brief to a local self-contained HTML file.

    Dry-run writes nothing. Apply, when eligible, renders the page, runs a fail-closed external-asset
    scan (refuses on any hit), writes the ``.html`` outside the repo (``<app_support>/html/`` by
    default), and records a V32 render receipt. The optional V28 agent receipt is emit-gated.
    """
    status = evaluate_daily_brief_html_render(brief_date=brief_date, db_path=db_path, now=now)
    dry_run = mode != "apply"
    status.mode = mode

    if dry_run:
        status.render_status = "preview"
    elif status.reason_code == HTML_RENDER_ELIGIBLE:
        payload = read_daily_brief_handoff(str(status.brief_run_id), db_path=db_path)
        if payload is None:  # pragma: no cover - defensive
            status.reason_code = HTML_RENDER_NEVER_GENERATED
            status.overall_status = "attention"
            status.render_status = "skipped"
            status.detail = "handoff_payload_missing"
        else:
            generated_label = (now or datetime.now(timezone.utc)).date().isoformat()
            rendered = render_daily_brief_html(payload, generated_label=generated_label)
            findings = _scan_html_for_external_assets(rendered)
            if findings:
                # Fail-closed: never write HTML that references an external asset / network.
                status.reason_code = HTML_RENDER_EXTERNAL_ASSET_BLOCKED
                status.overall_status = "attention"
                status.render_status = "skipped"
                status.no_external_assets = False
                status.external_asset_findings = len(findings)
                status.detail = "external_asset_or_network_reference_detected"
            else:
                target_dir = Path(html_dir) if html_dir is not None else PathPolicy().get_html_dir()
                target = target_dir / f"{status.brief_date}_daily_brief.html"
                _atomic_write_text(target, rendered)
                content_hash = _sha256(rendered)
                try:
                    redacted = str(target.relative_to(PathPolicy().get_app_support()))
                except ValueError:
                    redacted = f"{target.parent.name}/{target.name}"
                rendered_utc = datetime.now(timezone.utc).isoformat()
                status.reason_code = HTML_RENDER_COMPLETED
                status.render_status = "rendered"
                status.written = True
                status.content_hash = content_hash
                status.html_path_redacted = redacted
                status.html_path_hash = _sha256(str(target))
                status.rendered_utc = rendered_utc
                status.detail = "rendered_local_html"
                write_daily_brief_html_render_receipt(
                    brief_date=str(status.brief_date),
                    brief_run_id=status.brief_run_id,
                    render_status="rendered",
                    reason_code=HTML_RENDER_COMPLETED,
                    mode="apply",
                    content_hash=content_hash,
                    html_path_redacted=redacted,
                    html_path_hash=status.html_path_hash,
                    rendered_utc=rendered_utc,
                    db_path=db_path,
                )
    elif status.reason_code == HTML_RENDER_ALREADY_RENDERED:
        status.render_status = "already_rendered"
    else:
        status.render_status = "skipped"

    agent_run_id: str | None = None
    if emit_receipt:
        from .reasoning import build_agent_run_receipt
        from .store import write_agent_run_receipt

        receipt = build_agent_run_receipt(
            agent_id="daily_brief_html_render_agent",
            run_kind="daily_brief_html_render",
            status=status.overall_status,
            reason_code=status.reason_code,
            started_utc=status.generated_utc,
            finished_utc=datetime.now(timezone.utc).isoformat(),
        )
        agent_run_id = write_agent_run_receipt(receipt, db_path=db_path)
    return status, agent_run_id


# UI markers a self-contained brief must carry (asserted by the proof + tests).
_REQUIRED_UI_MARKERS = (
    'data-group="tier"',
    'data-group="project"',
    "sec-head",
    "evidence-drawer",
    "timeline",
    "review-panel",
    "@media print",
)


def build_daily_brief_html_render_proof() -> dict[str, Any]:
    """Deterministic proof (temp migrated DB + temp html dir) over all render paths."""
    import sqlite3
    import tempfile
    from datetime import timedelta

    from hb_assistant.construction.store import ConstructionStore

    now = datetime(2026, 6, 2, 21, 0, tzinfo=timezone.utc)

    def _insert_run(db: str, *, brief_run_id: str, status: str, generated_utc: str) -> None:
        conn = sqlite3.connect(db)
        with conn:
            conn.execute(
                "INSERT INTO daily_brief_runs (brief_run_id, brief_date, mode, status, generated_utc) "
                "VALUES (?, '2026-06-02', 'dry_run', ?, ?)",
                (brief_run_id, status, generated_utc),
            )
            conn.execute(
                "INSERT INTO daily_brief_handoff_lines (line_id, brief_run_id, section, line_index, "
                " title_redacted, review_tier, source_refs_json, generated_utc) "
                "VALUES (?, ?, 'priority_actions', 0, 'Follow up on RFI 042', 2, ?, ?)",
                (
                    uuid.uuid4().hex,
                    brief_run_id,
                    '[{"source_family": "procore", "source_ref": "rfi-042"}]',
                    generated_utc,
                ),
            )
        conn.close()

    with tempfile.TemporaryDirectory() as tmp:
        recent = (now - timedelta(hours=1)).isoformat()

        empty_db = f"{tmp}/empty.sqlite3"
        ConstructionStore(empty_db)
        never_run = evaluate_daily_brief_html_render(db_path=empty_db, now=now)

        blocked_db = f"{tmp}/blocked.sqlite3"
        ConstructionStore(blocked_db)
        _insert_run(
            blocked_db, brief_run_id=uuid.uuid4().hex, status="blocked", generated_utc=recent
        )
        blocked = evaluate_daily_brief_html_render(db_path=blocked_db, now=now)

        stale_db = f"{tmp}/stale.sqlite3"
        ConstructionStore(stale_db)
        _insert_run(
            stale_db,
            brief_run_id=uuid.uuid4().hex,
            status="synthesized",
            generated_utc=(now - timedelta(hours=72)).isoformat(),
        )
        stale = evaluate_daily_brief_html_render(db_path=stale_db, now=now)

        ok_db = f"{tmp}/ok.sqlite3"
        html_dir = f"{tmp}/html"
        ConstructionStore(ok_db)
        _insert_run(ok_db, brief_run_id="run-ok-1", status="synthesized", generated_utc=recent)

        preview = evaluate_daily_brief_html_render(db_path=ok_db, now=now)
        dry, _ = run_daily_brief_html_render_agent(
            db_path=ok_db, html_dir=html_dir, mode="dry_run", now=now
        )
        wrote_in_dry_run = Path(html_dir).exists()
        completed, _ = run_daily_brief_html_render_agent(
            db_path=ok_db, html_dir=html_dir, mode="apply", now=now
        )
        rendered_file = Path(html_dir) / "2026-06-02_daily_brief.html"
        rendered_exists = rendered_file.exists()
        rendered_html = rendered_file.read_text(encoding="utf-8") if rendered_exists else ""
        idempotent, _ = run_daily_brief_html_render_agent(
            db_path=ok_db, html_dir=html_dir, mode="apply", now=now
        )

    external_findings = _scan_html_for_external_assets(rendered_html)
    ui_present = all(m in rendered_html for m in _REQUIRED_UI_MARKERS)
    blob = _values_only_blob(
        [
            never_run.model_dump(),
            blocked.model_dump(),
            stale.model_dump(),
            preview.model_dump(),
            completed.model_dump(),
            idempotent.model_dump(),
        ]
    )
    no_raw_content = not any(t in blob for t in _FORBIDDEN_TOKENS)

    proof_passed = bool(
        never_run.reason_code == HTML_RENDER_NEVER_GENERATED
        and blocked.reason_code == HTML_RENDER_BLOCKED
        and stale.reason_code == HTML_RENDER_STALE
        and preview.reason_code == HTML_RENDER_ELIGIBLE
        and dry.render_status == "preview"
        and dry.written is False
        and not wrote_in_dry_run
        and completed.reason_code == HTML_RENDER_COMPLETED
        and completed.written is True
        and rendered_exists
        and ui_present
        and not external_findings
        and idempotent.reason_code == HTML_RENDER_ALREADY_RENDERED
        and no_raw_content
    )
    return {
        "proof": "phase_08b_daily_brief_html_render",
        "proof_passed": proof_passed,
        "never_generated_reason_code": never_run.reason_code,
        "blocked_reason_code": blocked.reason_code,
        "stale_reason_code": stale.reason_code,
        "eligible_reason_code": preview.reason_code,
        "completed_reason_code": completed.reason_code,
        "already_rendered_reason_code": idempotent.reason_code,
        "dry_run_wrote_nothing": not wrote_in_dry_run,
        "ui_components_present": ui_present,
        "no_external_assets": not external_findings,
        "no_raw_content": no_raw_content,
        "guardrails": {
            "local_first": True,
            "dry_run_default": True,
            "self_contained_no_network": True,
            "no_external_writeback": True,
            "no_external_delivery": True,
            "no_raw_html_persisted": True,
            "no_raw_content": True,
            "model_direct_external_api_access": False,
        },
    }
