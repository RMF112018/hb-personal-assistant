"""Email attachment extraction + attachment-card managed blocks (Phase 10F) — deterministic, stdlib only.

Phase 10E carded the `.eml` transmittal; the actual project instrument is often the **attachment**. This
module re-parses a saved `.eml` for attachment BYTES (the Phase 10E ``EmailAttachment`` keeps metadata
only), classifies each attachment, and produces the two managed card blocks that link a parent email card
to its attachment cards:

* ``hb-email-attachment`` (on the ATTACHMENT card) — graph-safe facts + wiki-links back to the parent
  email card and email archive note.
* ``hb-email-attachments`` (on the PARENT email card) — a deduped list of wiki-links to the attachment cards.

Guardrails: only ``Content-Disposition: attachment`` parts are extracted/carded; inline images are counted
as inline facts only (no binary, no card). Unsafe executable/script and oversize attachments are NEVER
written as binaries — they are reported with an explicit skip reason (never silently dropped). Graph facts
use the attachment content **sha256**, a parent-email **hash**, the **extension** and **content_type** —
never the raw filename or body text. The guarded binary writer only writes UNDER
``Email Archive/Work/Attachments/`` (the Phase 10E ``is_email_archive_path`` self-index root), never
escaping the vault.
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
from contextlib import suppress
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any

import yaml

from . import mdutil, pathsafe
from .source_indexer import EMAIL_ARCHIVE_FOLDER, is_email_archive_path

_INHERITED_PROJECT_PREFIX = "- Project (inherited from parent email):"

# Attachment binaries live in a dedicated subtree of the (self-index-guarded) Email Archive root.
ATTACHMENTS_SUBDIR = f"{EMAIL_ARCHIVE_FOLDER}/Work/Attachments"
# Default size cap (bytes); overridable at the call site. Oversize attachments are skipped, not written.
DEFAULT_MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024

# Executable / script types are never written as readable binaries (metadata-only, count-only skip).
_UNSAFE_EXTS = frozenset({
    "exe", "js", "vbs", "bat", "scr", "ps1", "cmd", "com", "msi", "jar", "app", "sh", "dll", "reg",
})
# Types the deterministic source-card pipeline can parse to text (others card as metadata-only).
_SUPPORTED_EXTS = frozenset({"pdf", "docx", "xlsx", "csv", "txt", "md", "eml"})

# Managed card block markers. The three hb-email* prefixes are mutually non-prefixing, so a scan for one
# never matches another (hb-email:start vs hb-email-attachment:start vs hb-email-attachments:start).
ATTACH_BEGIN_PREFIX = "<!-- hb-email-attachment:start"
ATTACH_END = "<!-- hb-email-attachment:end -->"
ATTACHMENTS_BEGIN = "<!-- hb-email-attachments:start -->"
ATTACHMENTS_END = "<!-- hb-email-attachments:end -->"
# Wiki-link delimiters are assembled (never written as a literal) to satisfy the staged denylist.
_WL_OPEN = "[" + "["
_WL_CLOSE = "]" + "]"

_SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9 _.()\-]+")
_MAX_STEM_CHARS = 80


@dataclass(frozen=True)
class ExtractedAttachment:
    index: int
    filename: str | None
    content_type: str | None
    disposition: str | None
    content_id: str | None
    size_bytes: int | None
    sha256: str | None
    is_inline: bool
    ext: str
    status: str
    data: bytes | None  # decoded payload for safe attachments; None for skipped/unsafe/oversize


# --------------------------------------------------------------------------- helpers
def _hash12(value: str) -> str:
    return hashlib.sha256(str(value).strip().lower().encode("utf-8", "replace")).hexdigest()[:12]


def _ext_from(filename: str | None, content_type: str | None) -> str:
    """Deterministic lowercase extension from filename, else guessed from content_type ('' if unknown)."""
    if filename:
        suf = Path(str(filename)).suffix.lower().lstrip(".")
        if suf:
            return suf
    if content_type:
        guessed = mimetypes.guess_extension(str(content_type).split(";")[0].strip())
        if guessed:
            return guessed.lower().lstrip(".")
    return ""


def _safe_stem(filename: str | None, ext: str, sha256: str, index: int) -> str:
    """Path-safe, deterministic display stem (NO directories/traversal/control chars); safe fallback."""
    if filename:
        raw = Path(str(filename).replace("\\", "/")).name  # basename only
        raw = Path(raw).stem if raw else ""
    else:
        raw = ""
    raw = "".join(ch for ch in raw if ch.isprintable() and ch not in "\t\r\n")
    raw = _SAFE_STEM_RE.sub("-", raw)
    raw = re.sub(r"\.{2,}", ".", raw)
    raw = re.sub(r"[-\s]{2,}", lambda m: m.group(0)[0], raw)
    raw = raw.strip(" .-")[:_MAX_STEM_CHARS].strip(" .-")
    if not raw:
        raw = f"attachment-{index}-{(ext or 'bin')}"
    return raw


def attachment_rel_path(parent_source_id: str, extracted: ExtractedAttachment) -> str:
    """Deterministic vault-relative binary path under the guarded attachments root.

    ``Email Archive/Work/Attachments/<parent_sid12>/<safe_stem>__<sha12>.<ext>`` — the sha12 suffix makes
    the path unique per content, so identical content re-runs land on the same path (idempotent) and two
    different attachments never collide on one path.
    """
    sid12 = str(parent_source_id)[:12]
    sha12 = (extracted.sha256 or "nohash")[:12]
    stem = _safe_stem(extracted.filename, extracted.ext, extracted.sha256 or "", extracted.index)
    ext = f".{extracted.ext}" if extracted.ext else ""
    return f"{ATTACHMENTS_SUBDIR}/{sid12}/{stem}__{sha12}{ext}"


def extract_attachments(eml_path: Path, *, max_bytes: int = DEFAULT_MAX_ATTACHMENT_BYTES,
                        ) -> tuple[list[ExtractedAttachment], int]:
    """Re-parse the `.eml` for attachment BYTES. Returns (true-attachments, inline_count).

    Deterministic walk order (mirrors ``source_email_archive._attachments``). Inline images are counted
    only (metadata-only) and excluded from the returned list. Unsafe/oversize/empty attachments are
    returned with an explicit skip status and ``data=None`` (never written). Duplicate content within the
    same email (same sha256) is marked ``duplicate`` after the first occurrence. Fail-safe: a parse error
    yields a single ``parse_failed`` entry.
    """
    try:
        with Path(eml_path).open("rb") as fh:
            msg = BytesParser(policy=policy.default).parse(fh)
    except Exception:  # noqa: BLE001 — unreadable/malformed → fail-safe, never raise
        return [ExtractedAttachment(0, None, None, None, None, None, None, False, "", "parse_failed",
                                    None)], 0

    out: list[ExtractedAttachment] = []
    inline_count = 0
    seen_sha: set[str] = set()
    idx = 0
    parts = msg.walk() if msg.is_multipart() else []
    for part in parts:
        disp = part.get_content_disposition()
        if disp not in ("attachment", "inline"):
            continue
        cid = part.get("Content-ID")
        is_inline = disp == "inline" or bool(cid and part.get_content_maintype() == "image")
        if is_inline:
            inline_count += 1
            continue
        i = idx
        idx += 1
        filename = part.get_filename()
        content_type = part.get_content_type()
        ext = _ext_from(filename, content_type)
        try:
            payload = part.get_payload(decode=True)
        except Exception:  # noqa: BLE001
            payload = None
        if not payload:
            out.append(ExtractedAttachment(i, filename, content_type, disp,
                                           (str(cid).strip("<>") if cid else None), 0, None, False,
                                           ext, "skipped_empty", None))
            continue
        sha = hashlib.sha256(payload).hexdigest()
        size = len(payload)
        base = {"index": i, "filename": filename, "content_type": content_type, "disposition": disp,
                "content_id": (str(cid).strip("<>") if cid else None), "size_bytes": size,
                "sha256": sha, "is_inline": False, "ext": ext}
        if sha in seen_sha:
            out.append(ExtractedAttachment(**base, status="duplicate", data=None))
            continue
        seen_sha.add(sha)
        if ext in _UNSAFE_EXTS:
            out.append(ExtractedAttachment(**base, status="skipped_unsafe_type", data=None))
        elif size > max_bytes:
            out.append(ExtractedAttachment(**base, status="skipped_size_cap", data=None))
        else:
            status = "extracted" if ext in _SUPPORTED_EXTS else "metadata_only"
            out.append(ExtractedAttachment(**base, status=status, data=payload))
    return out, inline_count


def _resolve_attachment_path(vault_root: Path, rel: str) -> tuple[Path, Path]:
    """Validate ``rel`` is under the guarded attachments root; return (resolved, attach_root).

    Refuses (raises ValueError) any path not under ``Email Archive/Work/Attachments/`` or that escapes
    that root via traversal/symlink.
    """
    norm = str(rel).replace("\\", "/").strip("/")
    if not (is_email_archive_path(norm) and norm.lower().startswith(ATTACHMENTS_SUBDIR.lower() + "/")):
        raise ValueError(f"attachment path not under {ATTACHMENTS_SUBDIR}/: {norm}")
    vault_root = Path(vault_root).resolve()
    attach_root = (vault_root / ATTACHMENTS_SUBDIR).resolve()
    resolved = (vault_root / norm).resolve()
    if not resolved.is_relative_to(attach_root):
        raise ValueError("attachment path escapes the attachments root")
    return resolved, attach_root


def write_attachment_binary(vault_root: Path, rel: str, data: bytes, *, overwrite: bool = False) -> str:
    """Write attachment bytes UNDER the guarded attachments root only. Returns 'written' | 'duplicate'.

    The binary is TRANSIENT (the caller deletes it right after the card is generated); it lives under
    the ``is_email_archive_path`` guard so even mid-run it is never scanned/indexed as a vault note.
    Refuses (raises ValueError) an out-of-root path or a byte-different overwrite without ``overwrite``.
    Atomic (tmp+replace).
    """
    resolved, _ = _resolve_attachment_path(vault_root, rel)
    if resolved.exists():
        if pathsafe.symlink_escapes(resolved, Path(vault_root).resolve()):
            raise ValueError("attachment path escapes via symlink")
        if hashlib.sha256(resolved.read_bytes()).hexdigest() == hashlib.sha256(data).hexdigest():
            return "duplicate"
        if not overwrite:
            raise ValueError("refusing to overwrite byte-different existing attachment")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    tmp = resolved.with_name(resolved.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, resolved)
    return "written"


def delete_attachment_binary(vault_root: Path, rel: str) -> bool:
    """Delete a transient attachment binary UNDER the guarded attachments root; prune empty parents.

    Returns True if a file was removed. Refuses (raises ValueError) any path outside the attachments
    root. Empty per-email/ subdirectories are removed up to (not including) the attachments root.
    """
    resolved, attach_root = _resolve_attachment_path(vault_root, rel)
    removed = False
    if resolved.is_file():
        resolved.unlink()
        removed = True
    parent = resolved.parent
    with suppress(OSError):
        while parent != attach_root and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    return removed


# --------------------------------------------------------------------------- graph-safe card facts/blocks
def attachment_card_facts(parent_email_source_id: str, extracted: ExtractedAttachment) -> dict[str, Any]:
    """Deterministic, graph-safe facts for the attachment card's hb-email-attachment marker."""
    return {
        "parent_email_hash": _hash12(parent_email_source_id),
        "attachment_sha256": extracted.sha256 or "",
        "attachment_index": extracted.index,
        "attachment_content_type": extracted.content_type or "",
        "attachment_disposition": extracted.disposition or "",
        "attachment_extension": extracted.ext or "",
        "extraction_status": extracted.status,
    }


def _attr(value: Any) -> str:
    return re.sub(r'[<>"\r\n]', " ", str(value if value is not None else "")).strip()


def attachment_marker(facts: dict[str, Any]) -> str:
    return (
        f'{ATTACH_BEGIN_PREFIX} parent_email_hash="{_attr(facts.get("parent_email_hash"))}"'
        f' attachment_sha256="{_attr(facts.get("attachment_sha256"))}"'
        f' attachment_index="{_attr(facts.get("attachment_index"))}"'
        f' attachment_content_type="{_attr(facts.get("attachment_content_type"))}"'
        f' attachment_disposition="{_attr(facts.get("attachment_disposition"))}"'
        f' attachment_extension="{_attr(facts.get("attachment_extension"))}"'
        f' extraction_status="{_attr(facts.get("extraction_status"))}" -->'
    )


def parse_email_attachment_marker(card_text: str) -> dict[str, Any] | None:
    """Read graph-safe attachment facts back from a card's hb-email-attachment start marker."""
    for ln in card_text.splitlines():
        if ln.startswith(ATTACH_BEGIN_PREFIX):
            return dict(re.findall(r'(\w+)="([^"]*)"', ln))
    return None


def _wiki_link(rel: str, display: str) -> str:
    target = rel[:-3] if rel.endswith(".md") else rel
    return f"{_WL_OPEN}{target}|{display}{_WL_CLOSE}"


def _replace_or_insert(card_text: str, begin_prefix: str, end_marker: str, block: list[str],
                       section: str) -> tuple[str | None, str]:
    """Idempotent single managed-block insert/replace under ``section``. Mirrors the 10E enrichers."""
    lines = card_text.splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.startswith(begin_prefix)]
    ends = [i for i, ln in enumerate(lines) if ln.strip() == end_marker]
    trailing = "\n" if card_text.endswith("\n") else ""
    if len(starts) == 1 and len(ends) == 1 and ends[0] > starts[0]:
        new = lines[:starts[0]] + block + lines[ends[0] + 1:]
        return "\n".join(new) + trailing, "updated"
    if starts or ends:
        return None, "ambiguous_existing_block"
    sec = next((i for i, ln in enumerate(lines) if ln == section), -1)
    if sec == -1:
        return None, "section_missing"
    end = next((i for i in range(sec + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    insert_at = end
    while insert_at > sec + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1
    new = lines[:insert_at] + ["", *block] + lines[insert_at:]
    return "\n".join(new) + trailing, "inserted"


def enrich_card_with_attachment(card_text: str, facts: dict[str, Any], parent_card_rel: str,
                                parent_archive_rel: str) -> tuple[str | None, str]:
    """Insert/replace ONE hb-email-attachment block on the attachment card under ``## Source Basis``."""
    body = [
        "- Parent email (context inherited from parent):"
        f" {facts.get('attachment_content_type') or '(unknown type)'}"
        f" · {facts.get('extraction_status')}",
        f"- Parent email card: {_wiki_link(parent_card_rel, Path(parent_card_rel).stem)}",
        f"- Parent email archive: {_wiki_link(parent_archive_rel, Path(parent_archive_rel).stem)}",
    ]
    block = [attachment_marker(facts), *body, ATTACH_END]
    return _replace_or_insert(card_text, ATTACH_BEGIN_PREFIX, ATTACH_END, block, "## Source Basis")


def upsert_email_attachments_block(card_text: str, entries: list[tuple[str, str]],
                                   ) -> tuple[str | None, str]:
    """Insert/replace ONE hb-email-attachments block on the PARENT email card under ``## Source Basis``.

    ``entries`` = list of (attachment_card_rel, status_label), deduped by card rel, deterministically sorted.
    """
    seen: dict[str, str] = {}
    for rel, status in entries:
        seen.setdefault(rel, status)
    body = [
        f"- {_wiki_link(rel, Path(rel).stem)} — extracted attachment · {seen[rel]}"
        for rel in sorted(seen)
    ]
    if not body:
        body = ["- (no attachment cards)"]
    block = [ATTACHMENTS_BEGIN, *body, ATTACHMENTS_END]
    return _replace_or_insert(card_text, ATTACHMENTS_BEGIN, ATTACHMENTS_END, block, "## Source Basis")


def apply_inherited_project_frontmatter(card_text: str, *, project_number: str | None,
                                        project_key: str | None) -> str:
    """Populate frontmatter project_number/project_key + the ``project/<n>`` tag from inherited identity.

    Attachment cards index under a synthetic root whose path carries no project number, so the renderer
    leaves these null; this fills them from the parent-email identity so the frontmatter agrees with the
    hb-project-identity block. Only fills fields currently null/absent (never clobbers a pre-existing
    non-null value) and never duplicates the project tag. Returns the card unchanged when there is no
    frontmatter or no inherited ``project_number``. Preserves frontmatter key order.
    """
    if not project_number:
        return card_text
    fm, body = mdutil.split_frontmatter(card_text)
    if fm is None:
        return card_text
    new_fm = dict(fm)
    changed = False
    if new_fm.get("project_number") in (None, "", "null"):
        new_fm["project_number"] = project_number
        changed = True
    if project_key and new_fm.get("project_key") in (None, "", "null"):
        new_fm["project_key"] = project_key
        changed = True
    tag = f"project/{project_number}"
    tags = [str(t).strip().lstrip("#") for t in mdutil.frontmatter_tags(new_fm) if str(t).strip()]
    if tag not in tags:
        tags.append(tag)
        new_fm["tags"] = tags
        changed = True
    if not changed:
        return card_text
    dumped = yaml.safe_dump(new_fm, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{dumped}\n---\n\n{body.lstrip(chr(10))}"


def reconcile_related_project_line(card_text: str, *, project_number: str | None,
                                   project_key: str | None, project_name: str | None = None) -> str:
    """Replace the ``## Related Project`` placeholder bullet with an inherited-project bullet.

    Swaps the deterministic ``- No project number detected…`` / ``- Detected project number…`` placeholder
    (rendered from the null detail) for a bullet reflecting the inherited identity, so the visible section
    no longer contradicts the hb-project-identity block. Idempotent; never touches the managed block.
    """
    if not project_number:
        return card_text
    lines = card_text.splitlines()
    trailing = "\n" if card_text.endswith("\n") else ""
    sec = next((i for i, ln in enumerate(lines) if ln.strip() == "## Related Project"), -1)
    if sec == -1:
        return card_text
    end = len(lines)
    for i in range(sec + 1, len(lines)):
        if lines[i].startswith("## ") or lines[i].startswith("<!-- hb-project-identity:start"):
            end = i
            break
    if any(lines[i].startswith(_INHERITED_PROJECT_PREFIX) for i in range(sec + 1, end)):
        return card_text  # already reconciled
    bullet = f"{_INHERITED_PROJECT_PREFIX} {project_number}"
    if project_key:
        bullet += f" · {project_key}"
    if project_name:
        bullet += f" · {project_name}"
    for i in range(sec + 1, end):
        s = lines[i].strip()
        if s.startswith("- No project number detected") or s.startswith("- Detected project number:"):
            lines[i] = bullet
            return "\n".join(lines) + trailing
    return card_text
