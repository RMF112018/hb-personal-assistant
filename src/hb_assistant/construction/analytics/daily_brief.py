"""Daily Brief external Markdown file service (Prompt 10 / UI-10).

App role: detect / parse / polish / present only.
Generation owner: external desktop AI platform (Claude, ChatGPT, Perplexity, Other).
The service never generates, rewrites, or authors brief content. It loads a user-provided
local folder + naming pattern, detects the latest matching .md, computes one of the 7
contracted states, performs light heading-based section extraction when practical, and
returns structured metadata + advisory payload for the UI renderer.

Config is persisted as a small JSON under Application Support (outside repo). No tokens,
raw sources, or secrets are handled here. All responses embed guardrails and the
"presenter only" contract.
"""

from __future__ import annotations

import contextlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": False,
    "platform": "other",
    "output_folder": None,
    "file_pattern": "HB-Daily-Brief-*.md",
    "stale_threshold_minutes": 24 * 60,
    "show_on_today": True,
}

RECOMMENDED_SECTIONS = [
    "Executive Summary",
    "Today's Meetings",
    "Projects Needing Attention",
    "Cost / Change Exposure Signals",
    "Aging RFIs / Submittals / Decisions",
    "Correspondence Worth Reviewing",
    "Documents Changed or Requiring Review",
    "Vendor / Subcontractor Attention Items",
    "Billing / Cash / Retention Attention Items",
    "Data Confidence Notes",
]

STATE_LABELS: dict[str, str] = {
    "not_configured": "Not configured",
    "external_ai_setup_required": "External AI setup required",
    "configured_waiting": "Configured, waiting for next run",
    "brief_available": "Brief available",
    "brief_stale": "Brief stale",
    "brief_generation_failed": "Brief generation failed",
    "markdown_parse_warning": "Markdown parse warning",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _guardrails() -> dict[str, Any]:
    return {
        "read_only": True,
        "local_first": True,
        "no_cli_shellout": True,
        "no_external_writeback": True,
        "sensitive_field_values_excluded": True,
        "makes_determination": False,
        "advisory_only": True,
        "presenter_only": True,
        "daily_brief_generation_owner": "external_desktop_ai_platform",
        "app_role": "detect_parse_polish_present",
        "no_raw_sensitive_response_fields": True,
    }


def _presenter_advisory() -> str:
    return (
        "Daily Brief is generated externally by a desktop AI platform/agent as a Markdown file. "
        "This app detects the file, validates freshness, parses headings/sections when practical, "
        "and presents a polished executive view. The app is a presenter/formatter only and does not "
        "generate, author, or materially rewrite the brief. Configure the external agent to write the "
        "file (MCP where supported) and never paste raw tokens, full bodies, or secrets."
    )


def _config_path() -> Path:
    pp = PathPolicy()
    base = pp.get_app_support() / "analytics"
    base.mkdir(parents=True, exist_ok=True)
    return base / "daily_brief_ui_config.json"


def _load_config() -> dict[str, Any]:
    p = _config_path()
    cfg = dict(DEFAULT_CONFIG)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update({k: data[k] for k in cfg if k in data})
        except Exception:
            # Fail closed to defaults; never block UI on bad config file.
            pass
    return cfg


def _save_config(updates: dict[str, Any]) -> dict[str, Any]:
    cfg = _load_config()
    for k, v in updates.items():
        if k in cfg:
            cfg[k] = v
    p = _config_path()
    with contextlib.suppress(Exception):
        # Best effort; return what we have.
        p.write_text(json.dumps(cfg, indent=2, sort_keys=True), encoding="utf-8")
    return cfg


def _normalize_platform(p: str | None) -> str:
    if not p:
        return "other"
    p = p.lower().strip()
    if p in {"claude", "chatgpt", "perplexity"}:
        return p
    return "other"


def _resolve_folder(folder: str | None) -> Path | None:
    if not folder or not isinstance(folder, str):
        return None
    try:
        p = Path(folder).expanduser().resolve()
        return p
    except Exception:
        return None


def _find_latest_file(folder: Path, pattern: str) -> Path | None:
    try:
        if not folder.exists() or not folder.is_dir():
            return None
        matches = list(folder.glob(pattern))
        if not matches:
            # Also try common variants if user used a broad pattern
            matches = list(folder.glob("*.md"))
        if not matches:
            return None
        # Latest by mtime, tie-break by name
        matches.sort(key=lambda f: (f.stat().st_mtime, f.name), reverse=True)
        return matches[0]
    except Exception:
        return None


def _parse_sections(text: str) -> tuple[dict[str, str], list[str]]:
    """Light, safe heading splitter. Returns (canonical_sections, warnings)."""
    warnings: list[str] = []
    if not text or not text.strip():
        return {}, ["empty_content"]
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        m = re.match(r"^\s*#\s+(.+?)\s*$", line)
        if m:
            heading = m.group(1).strip()
            current = heading
            if current not in sections:
                sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    # Map to recommended canonical where possible (case-insensitive contains or exact)
    canonical: dict[str, str] = {}
    lower_map = {h.lower(): h for h in sections}
    for rec in RECOMMENDED_SECTIONS:
        rec_l = rec.lower()
        if rec_l in lower_map:
            src = lower_map[rec_l]
            body = "\n".join(sections[src]).strip()
            canonical[rec] = body[:4000]  # bounded
        else:
            # fuzzy: any heading containing key tokens
            for h in sections:
                if rec_l.split()[0] in h.lower():
                    body = "\n".join(sections[h]).strip()
                    canonical[rec] = body[:4000]
                    break
    if not canonical and sections:
        # At least keep first few raw headings as "other"
        for h, lines in list(sections.items())[:3]:
            canonical[h] = "\n".join(lines).strip()[:2000]
    if not canonical:
        warnings.append("no_sections_parsed")
    # Warn on very short brief
    if len(text) < 200:
        warnings.append("very_short_content")
    return canonical, warnings


def _compute_state(
    *,
    enabled: bool,
    folder: str | None,
    file_path: Path | None,
    mtime: float | None,
    threshold_mins: int,
    parse_warnings: list[str],
) -> tuple[str, str]:
    if not enabled or not folder:
        return "not_configured", STATE_LABELS["not_configured"]
    if not file_path:
        return "configured_waiting", STATE_LABELS["configured_waiting"]
    try:
        now = time.time()
        age_mins = (now - (mtime or now)) / 60.0
    except Exception:
        age_mins = 10**9
    if age_mins > threshold_mins:
        return "brief_stale", STATE_LABELS["brief_stale"]
    if parse_warnings:
        return "markdown_parse_warning", STATE_LABELS["markdown_parse_warning"]
    return "brief_available", STATE_LABELS["brief_available"]


class DailyBriefService:
    """Framework-free service for external Daily Brief config + FS detection + presentation."""

    def __init__(self) -> None:
        self._pp = PathPolicy()

    def load_config(self) -> dict[str, Any]:
        return _load_config()

    def save_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        # Normalize a few fields
        if "platform" in updates:
            updates["platform"] = _normalize_platform(updates["platform"])
        if "stale_threshold_minutes" in updates:
            try:
                updates["stale_threshold_minutes"] = max(
                    30, int(updates["stale_threshold_minutes"])
                )
            except Exception:
                updates["stale_threshold_minutes"] = DEFAULT_CONFIG["stale_threshold_minutes"]
        if "output_folder" in updates and updates["output_folder"]:
            # Store as provided (user controls); resolution happens at detect time.
            pass
        return _save_config(updates)

    def validate_output_folder(self, folder: str | None) -> dict[str, Any]:
        p = _resolve_folder(folder)
        if not p:
            return {
                "valid": False,
                "exists": False,
                "is_dir": False,
                "writable": False,
                "message": "No folder provided or path could not be resolved.",
                "guardrails": _guardrails(),
                "advisory": _presenter_advisory(),
            }
        exists = p.exists()
        is_dir = p.is_dir() if exists else False
        writable = False
        if exists and is_dir:
            # Best-effort write test (temp file in dir)
            test_f = p / f".hb_daily_brief_write_test_{int(time.time())}.tmp"
            try:
                test_f.write_text("ok", encoding="utf-8")
                test_f.unlink(missing_ok=True)
                writable = True
            except Exception:
                writable = False
        msg = (
            "Folder ready."
            if (exists and is_dir and writable)
            else "Folder not ready or not writable by current user."
        )
        if not exists:
            msg = "Folder does not exist. Create it before the external agent runs."
        elif not is_dir:
            msg = "Path exists but is not a directory."
        elif not writable:
            msg = "Directory exists but is not writable by this process."
        return {
            "valid": bool(exists and is_dir and writable),
            "exists": exists,
            "is_dir": is_dir,
            "writable": writable,
            "path": str(p),
            "message": msg,
            "guardrails": _guardrails(),
            "advisory": _presenter_advisory(),
        }

    def detect_latest(self, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
        cfg = cfg or self.load_config()
        enabled = bool(cfg.get("enabled"))
        platform = _normalize_platform(cfg.get("platform"))
        folder = cfg.get("output_folder")
        pattern = str(cfg.get("file_pattern") or DEFAULT_CONFIG["file_pattern"])
        threshold = int(
            cfg.get("stale_threshold_minutes") or DEFAULT_CONFIG["stale_threshold_minutes"]
        )

        resolved = _resolve_folder(folder)
        file_path = _find_latest_file(resolved, pattern) if resolved else None

        mtime = None
        size = None
        content = None
        sections: dict[str, str] = {}
        parse_warnings: list[str] = []
        state = "not_configured"
        label = STATE_LABELS["not_configured"]

        if file_path:
            try:
                st = file_path.stat()
                mtime = st.st_mtime
                size = st.st_size
                # Bounded read for safety
                raw = file_path.read_text(encoding="utf-8", errors="replace")
                content = raw[:100000]  # generous but bounded for a daily brief
                sections, parse_warnings = _parse_sections(raw)
            except Exception as e:
                parse_warnings = [f"read_error:{type(e).__name__}"]
                state, label = "brief_generation_failed", STATE_LABELS["brief_generation_failed"]

        if state != "brief_generation_failed":
            state, label = _compute_state(
                enabled=enabled,
                folder=folder,
                file_path=file_path,
                mtime=mtime,
                threshold_mins=threshold,
                parse_warnings=parse_warnings,
            )

        generated_at = None
        if mtime:
            with contextlib.suppress(Exception):
                generated_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

        payload: dict[str, Any] = {
            "surface": "analytics.daily_brief",
            "generated_utc": _utc_now(),
            "state": state,
            "label": label,
            "config": {
                "enabled": enabled,
                "platform": platform,
                "output_folder": folder,
                "file_pattern": pattern,
                "stale_threshold_minutes": threshold,
                "show_on_today": bool(cfg.get("show_on_today", True)),
            },
            "last_file": {
                "path": str(file_path) if file_path else None,
                "mtime_utc": generated_at,
                "size_bytes": size,
            },
            "is_stale": state == "brief_stale",
            "parse_warnings": parse_warnings,
            "sections": sections,
            "content": content,
            "advisory": _presenter_advisory(),
            "guardrails": _guardrails(),
            "presenter_only": True,
        }
        return payload

    def get_status(self) -> dict[str, Any]:
        cfg = self.load_config()
        # Lightweight detect (no full content) for status surfaces
        full = self.detect_latest(cfg)
        # Strip heavy content for status
        status = {k: v for k, v in full.items() if k not in ("content", "sections")}
        status["surface"] = "analytics.daily_brief.status"
        # Provide a compact last_file summary
        lf = full.get("last_file", {})
        status["last_file"] = lf
        status["state"] = full.get("state")
        status["label"] = full.get("label")
        return status

    def get_latest(self) -> dict[str, Any]:
        full = self.detect_latest()
        full["surface"] = "analytics.daily_brief.latest"
        return full

    def configure(self, updates: dict[str, Any]) -> dict[str, Any]:
        cfg = self.save_config(updates)
        # Return fresh status after save
        status = self.get_status()
        status["config"] = cfg  # echo saved
        status["surface"] = "analytics.daily_brief.configured"
        return status

    def generate_setup_instructions(
        self, platform: str | None = None, overrides: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        cfg = self.load_config()
        if overrides:
            cfg.update(overrides)
        plat = _normalize_platform(platform or cfg.get("platform"))
        folder = cfg.get("output_folder") or "~/Documents/HB-Daily-Briefs"
        pattern = cfg.get("file_pattern") or "HB-Daily-Brief-*.md"
        threshold = cfg.get("stale_threshold_minutes") or 1440

        mcp_note = (
            "If your platform supports local MCP servers (e.g. Claude Desktop), connect it to the "
            "HB Personal Assistant MCP tools (hb_get_*, hb_search_*) for fresh, redacted construction "
            "context. The scheduled prompt below instructs the agent to use tools where available."
        )
        if plat == "claude":
            platform_specific = (
                "Claude: Use a Project or custom instruction with daily/ recurring schedule. "
                "Enable file output or Artifacts + save the MD to the target folder. "
                "Connect MCP if the hb- server is running locally."
            )
        elif plat == "chatgpt":
            platform_specific = (
                "ChatGPT: Use a Custom GPT with scheduled actions or a local automation (e.g. via "
                "Shortcuts / cron + the prompt) that can write the file. Save the produced Markdown "
                "to the folder with the naming pattern."
            )
        elif plat == "perplexity":
            platform_specific = (
                "Perplexity: Paste the prompt into a scheduled or recurring query if supported, or "
                "run manually daily and save the answer as .md to the folder. Manual save is the "
                "common fallback."
            )
        else:
            platform_specific = (
                "Other: Use your platform's scheduler, recurring prompt, or local script. "
                "Ensure the final output is saved as a .md file to the configured folder."
            )

        scheduled = self._build_scheduled_prompt(plat, folder, pattern, threshold)

        return {
            "surface": "analytics.daily_brief.setup_instructions",
            "generated_utc": _utc_now(),
            "platform": plat,
            "mcp_setup_note": mcp_note,
            "platform_specific": platform_specific,
            "output_instructions": f"Create the folder if needed: {folder}. Ensure the external agent can write files there.",
            "stale_threshold_note": f"Stale threshold in UI is {threshold} minutes. External runs should complete before the threshold for 'available' state.",
            "scheduled_prompt": scheduled,
            "test_steps": "After the first scheduled or manual run, use 'Test detection' or 'Validate folder' in Settings, then check the Daily Brief section on Today.",
            "advisory": _presenter_advisory(),
            "guardrails": _guardrails(),
        }

    def _build_scheduled_prompt(
        self, platform: str, folder: str, pattern: str, threshold: int
    ) -> str:
        today_token = "YYYY-MM-DD"  # user replaces or agent uses current date
        base = f"""You are a precise, construction-focused Daily Brief generator for a single CM user.

Produce an executive Daily Brief in clean Markdown for today.

Strict output contract:
- Output ONLY the Markdown (no extra prose outside the file).
- Save the file to this exact local path: {folder}
- Use this file name pattern for today's date: {pattern} (use current date in place of {today_token}).
- Structure with the following sections as H1 or H2 headings (include the heading even if noting limited data):
  1. Executive Summary
  2. Today's Meetings
  3. Projects Needing Attention
  4. Cost / Change Exposure Signals
  5. Aging RFIs / Submittals / Decisions
  6. Correspondence Worth Reviewing
  7. Documents Changed or Requiring Review
  8. Vendor / Subcontractor Attention Items
  9. Billing / Cash / Retention Attention Items
  10. Data Confidence Notes

Mandatory rules (do not violate):
- Advisory and observational only. Never make legal, safety, claims, schedule guarantee, or financial determinations.
- Never emit raw tokens, full email bodies, passwords, PEMs, unredacted deltas, or live links that could leak.
- When context for a section is thin or missing, write exactly: "Insufficient context for <section>. Recommend direct review in the source system."
- Prefer project keys, redacted message ids, or short titles over full content.
- End the brief with a short "Generation note" line: "Externally generated for HB Personal Assistant — presents/polishes only."

Data sources: Use any connected MCP tools (hb_get_*, hb_search_*, etc.) for fresh redacted context from mail, calendar, Procore, files, and local records. If no MCP/tools, use the best available context the user has provided in this session or prior.

After writing the file, output a one-line confirmation with the absolute path and byte size.

Current date context: use the local calendar date for the file name and any "as of" headers.
"""
        plat_note = {
            "claude": "\nClaude note: Schedule via Claude Projects / custom instructions or a desktop automation. Connect the local HB MCP server if available for tool-assisted context.",
            "chatgpt": "\nChatGPT note: Run via a Custom GPT + scheduled automation or local script that can persist the file. Manual copy of the MD into the target folder is acceptable fallback.",
            "perplexity": "\nPerplexity note: Run the prompt on a recurring basis and save the answer as .md to the target folder with the naming pattern.",
            "other": "\nOther platform: Use whatever scheduling or recurring mechanism is available. Ensure the final Markdown lands at the specified folder + pattern.",
        }.get(platform, "")

        threshold_note = f"\nFreshness: The UI will consider the brief stale after {threshold} minutes. Aim to complete generation and file write before the user's typical morning review window."

        return base + plat_note + threshold_note

    def build_today_presentation(self) -> dict[str, Any]:
        """Payload shaped for /api/today/daily-brief and the Today Daily Brief section renderer."""
        full = self.detect_latest()
        # Keep it compact but rich enough for the 7-state renderer + open action
        return {
            "surface": "analytics.today.daily_brief",
            "generated_utc": full.get("generated_utc"),
            "status": full.get("state"),
            "label": full.get("label"),
            "content": full.get("content"),
            "markdown": full.get("content"),
            "sections": full.get("sections", {}),
            "path": full.get("last_file", {}).get("path"),
            "generated_at": full.get("last_file", {}).get("mtime_utc"),
            "warnings": full.get("parse_warnings", []),
            "is_stale": full.get("is_stale", False),
            "config": full.get("config", {}),
            "advisory": full.get("advisory"),
            "guardrails": full.get("guardrails", _guardrails()),
            "presenter_only": True,
        }


# Convenience for direct CLI or tests (not used by UI routes).
def build_daily_brief_status() -> dict[str, Any]:
    return DailyBriefService().get_status()


def build_daily_brief_latest() -> dict[str, Any]:
    return DailyBriefService().get_latest()
