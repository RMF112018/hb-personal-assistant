"""N8C-23 Obsidian card / receipt / manifest renderers.

Deterministic, organization-neutral markdown. Every body passes through the NAS ``redact_text`` guard so a
promoted card can never leak a bearer token, credential field, PEM, or API key. Frontmatter is emitted with
``yaml.safe_dump`` (same convention as the existing writer layer).
"""

from __future__ import annotations

from typing import Any

import yaml

from hb_assistant.nas_mcp.redaction import redact_text

_REQUIRED_TAG_PREFIXES = ("second-brain/canonical", "artifact/", "status/", "source/", "domain/")


def _wikilink(target: str | None) -> str:
    t = (target or "").strip()
    return f"[[{t}]]" if t else ""


def required_tags(artifact_type: str, source_client: str, domain: str, review_state: str) -> list[str]:
    return [
        "second-brain/canonical",
        f"artifact/{artifact_type}",
        f"status/{review_state or 'approved'}",
        f"source/{(source_client or 'unknown')}",
        f"domain/{(domain or 'unknown')}",
    ]


def _frontmatter(mapping: dict[str, Any]) -> str:
    body = yaml.safe_dump(mapping, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{body}---\n"


def render_artifact_card(
    artifact: dict[str, Any],
    *,
    promotion_receipt_id: str | None = None,
    related_artifacts: list[str] | None = None,
    review_history: list[dict[str, Any]] | None = None,
    future_use_guidance: str = "",
) -> tuple[str, bool]:
    """Render one canonical artifact card. Returns (markdown, redaction_applied)."""
    atype = str(artifact.get("artifact_type", "knowledge_note"))
    domain = str(artifact.get("domain") or "unknown")
    source_client = str(artifact.get("source_client") or "unknown")
    review_state = str(artifact.get("review_state") or "approved")
    tags = required_tags(atype, source_client, domain, review_state)
    tags += [t for t in (artifact.get("extra_tags") or []) if t not in tags]
    related = list(related_artifacts or artifact.get("related_artifacts") or [])

    fm = {
        "canonical_id": artifact.get("canonical_id"),
        "artifact_type": atype,
        "status": artifact.get("status", "canonical"),
        "title": artifact.get("title"),
        "domain": domain,
        "source_client": source_client,
        "source_session_id": artifact.get("source_session_id"),
        "proposal_id": artifact.get("source_proposal_id"),
        "promotion_receipt_id": promotion_receipt_id or artifact.get("promotion_receipt_id"),
        "review_state": review_state,
        "version": int(artifact.get("version", 1)),
        "created_at": artifact.get("created_at"),
        "promoted_at": artifact.get("promoted_at"),
        "supersedes": list(artifact.get("supersedes") or []),
        "superseded_by": artifact.get("superseded_by_canonical_id"),
        "related_artifacts": related,
        "tags": tags,
    }

    summary, r1 = redact_text(str(artifact.get("summary") or ""))
    body, r2 = redact_text(str(artifact.get("body_markdown") or ""))

    lines = [
        f"# {artifact.get('title', 'Untitled')}",
        "",
        "## Summary",
        summary or "_(no summary)_",
        "",
        "## Artifact",
        body or "_(no body)_",
        "",
        "## Source Session",
        _wikilink(artifact.get("source_session_id")) or "_(none)_",
        "",
        "## Related Artifacts",
    ]
    lines += ([f"- {_wikilink(r)}" for r in related] or ["_(none)_"])
    lines += ["", "## Review History"]
    if review_history:
        for r in review_history:
            lines.append(f"- {r.get('decision','?')} — {r.get('created_at','')} {r.get('review_notes','') or ''}".rstrip())
    else:
        lines.append("_(none)_")
    lines += [
        "",
        "## Future Use Guidance",
        (future_use_guidance or "Retrieve via the N8C assistant/canonical tools using this canonical_id."),
        "",
        "## Promotion Receipt",
        _wikilink(promotion_receipt_id or artifact.get("promotion_receipt_id")) or "_(none)_",
        "",
    ]
    return _frontmatter(fm) + "\n".join(lines) + "\n", (r1 or r2)


def render_receipt_card(receipt: dict[str, Any], *, created_paths: list[str]) -> str:
    fm = {
        "note_type": "promotion_receipt",
        "promotion_receipt_id": receipt.get("promotion_receipt_id"),
        "promotion_bundle_id": receipt.get("promotion_bundle_id"),
        "session_id": receipt.get("session_id"),
        "status": receipt.get("status"),
        "validation_hash": receipt.get("validation_hash"),
        "created_at": receipt.get("created_at"),
        "tags": ["second-brain/canonical", "artifact/promotion_receipt", "topic/structured-intelligence"],
    }
    lines = [
        f"# Canonical Artifact Promotion Receipt {receipt.get('promotion_receipt_id','')}",
        "",
        "## Counts",
        f"- created: {receipt.get('created_count', 0)}",
        f"- updated: {receipt.get('updated_count', 0)}",
        f"- superseded: {receipt.get('superseded_count', 0)}",
        f"- archived: {receipt.get('archived_count', 0)}",
        f"- failed: {receipt.get('failed_count', 0)}",
        "",
        "## Created Cards",
    ]
    lines += ([f"- `{p}`" for p in created_paths] or ["_(none)_"])
    lines += ["", f"Status: **{receipt.get('status','')}**", ""]
    return _frontmatter(fm) + "\n".join(lines) + "\n"


def render_canonical_manifest_md(entries: list[dict[str, Any]], *, generated_at: str, runtime_commit: str) -> str:
    fm = {
        "note_type": "canonical_artifact_manifest",
        "generated_at": generated_at,
        "generated_from_runtime_commit": runtime_commit,
        "entry_count": len(entries),
        "tags": ["second-brain/canonical", "topic/structured-intelligence", "topic/memory"],
    }
    lines = ["# Canonical Artifact Manifest", "", f"Total: {len(entries)}", "",
             "| canonical_id | type | status | domain | vault_path |", "|---|---|---|---|---|"]
    for e in entries:
        lines.append(
            f"| {e.get('canonical_id','')} | {e.get('artifact_type','')} | {e.get('status','')} "
            f"| {e.get('domain','')} | `{e.get('vault_path','')}` |"
        )
    lines.append("")
    return _frontmatter(fm) + "\n".join(lines) + "\n"
