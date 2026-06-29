"""Deterministic construction-document analysis for indexed sources.

Pure, side-effect-free heuristics (regex + filename/path + bounded indexed text) that extract
PM-relevant facts from an already-indexed source ``detail`` dict. NO LLM, NO file/network I/O, NO
new dependencies — this never re-reads the file; it works only from the bounded excerpt the indexer
already stored (``text_excerpt``; ``None`` for sensitive sources) plus ``rel_path``/``file_ext``.

The result drives PM-grade card sections, structured frontmatter, the typed advisory prompt, and
referenced-sheet relationship matching. Every extracted list is bounded so cards/prompts stay small.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Bounds — keep cards and prompts small and predictable.
_MAX_ITEMS = 25
_MAX_ITEM_CHARS = 200
_MAX_SCAN_LINES = 400

DRAWING_DOCUMENT_TYPES = frozenset(
    {"architectural_drawing", "structural_drawing", "mep_drawing", "civil_drawing"}
)

# Sheet-number discipline prefixes (longest first so 'FP'/'FA' beat 'F').
_DISCIPLINE_BY_PREFIX: tuple[tuple[str, str, str], ...] = (
    ("FP", "fire_protection", "mep_drawing"),
    ("FA", "fire_protection", "mep_drawing"),
    ("LV", "low_voltage", "mep_drawing"),
    ("A", "architectural", "architectural_drawing"),
    ("S", "structural", "structural_drawing"),
    ("E", "electrical", "mep_drawing"),
    ("M", "mechanical", "mep_drawing"),
    ("P", "plumbing", "mep_drawing"),
    ("C", "civil", "civil_drawing"),
)

# A sheet reference like A-312, S-101, FP-201, M-3.2. Prefix 1-2 letters, 2-4 digit number.
_SHEET_RE = re.compile(r"\b([A-Z]{1,2})-(\d{2,4}(?:\.\d+)?)\b")
_REV_NUM_RE = re.compile(r"\bRev(?:ision)?\.?\s*([0-9]{1,2})\b", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b")
_SCALE_RE = re.compile(r"\b\d{1,2}/\d{1,2}\"?\s*=\s*\d{1,2}'\s*-\s*\d{1,2}\"")
_DATUM_RE = re.compile(r"^(.{0,48}?)\s*([+-]?\d{1,3}'\s*-\s*\d{1,2}\")\s*$")
_NOTE_RE = re.compile(r"^\s*(\d{1,2})\.\s+(\S.{2,})$")
_SPACE_RE = re.compile(r"\b([A-Z][A-Z][A-Z &/+.-]{2,40}?)\s+(\d{3})\b")

_ISSUE_STATUSES = (
    "PERMIT DOCUMENTS", "PERMIT SET", "FOR PERMIT", "CONSTRUCTION DOCUMENTS",
    "FOR CONSTRUCTION", "ISSUED FOR CONSTRUCTION", "BID SET", "BID DOCUMENTS",
    "FOR BID", "SCHEMATIC DESIGN", "DESIGN DEVELOPMENT", "ADDENDUM", "NOT FOR CONSTRUCTION",
)

# Coordination keyword -> normalized PM flag. Scanned case-insensitively over the excerpt.
_COORD_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("waterproof", "waterproofing"),
    ("vapor barrier", "vapor barrier"),
    ("air barrier", "air/vapor barrier"),
    ("expansion joint", "expansion joints"),
    ("curtain wall", "curtain wall/storefront"),
    ("storefront", "curtain wall/storefront"),
    ("sbs", "built-up SBS roofing"),
    ("built-up roof", "built-up roofing"),
    ("roof assembly", "roof assembly"),
    ("parapet", "parapet/coping"),
    ("coping", "parapet/coping"),
    ("cmu", "CMU / structural coordination"),
    ("masonry", "masonry coordination"),
    ("delegated", "delegated-design shop drawings"),
    ("shop drawing", "shop drawings"),
    ("ceiling framing", "exterior ceiling framing shop drawings"),
    ("storefront glazing", "glazing coordination"),
    ("glazing", "glazing coordination"),
    ("footing", "footing/foundation coordination"),
    ("slab", "slab/foundation coordination"),
    ("structural", "structural coordination"),
)

_SUBMITTAL_KEYWORDS = ("submittal", "shop drawing", "product data", "sample", "mock-up", "mockup")


def _clip(value: str) -> str:
    return value.strip()[:_MAX_ITEM_CHARS]


def _dedup(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        v = _clip(v)
        if v and v not in seen:
            seen.add(v)
            out.append(v)
        if len(out) >= _MAX_ITEMS:
            break
    return out


@dataclass(frozen=True)
class SourceAnalysis:
    """Deterministic, bounded facts extracted from an indexed source."""

    document_type: str = "general_document"
    discipline: str = "unknown"
    sheet_number: str | None = None
    sheet_title: str | None = None
    project_name: str | None = None
    project_address: str | None = None
    issue_status: str | None = None
    revision_number: str | None = None
    revision_date: str | None = None
    revision_description: str | None = None
    scale: str | None = None
    entities: list[str] = field(default_factory=list)
    spaces: list[str] = field(default_factory=list)
    datums: list[str] = field(default_factory=list)
    numbered_notes: list[str] = field(default_factory=list)
    referenced_sheets: list[str] = field(default_factory=list)
    submittal_requirements: list[str] = field(default_factory=list)
    coordination_flags: list[str] = field(default_factory=list)
    pm_followup_categories: list[str] = field(default_factory=list)

    @property
    def is_drawing(self) -> bool:
        return self.document_type in DRAWING_DOCUMENT_TYPES

    def to_frontmatter_dict(self) -> dict[str, str]:
        """Scalar fields suitable for card frontmatter; omits None/empty values."""
        out: dict[str, str] = {"document_type": self.document_type}
        if self.discipline and self.discipline != "unknown":
            out["discipline"] = self.discipline
        for key in ("sheet_number", "sheet_title", "issue_status",
                    "revision_number", "revision_date", "revision_description"):
            value = getattr(self, key)
            if value:
                out[key] = str(value)
        return out

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sheet_number_from_filename(rel_path: str) -> tuple[str | None, str, str]:
    """Return (sheet_number, discipline, document_type_guess) from the filename stem."""
    stem = Path(rel_path).stem.upper()
    m = _SHEET_RE.search(stem.replace("REV", " REV"))
    if not m:
        return None, "unknown", "general_pdf" if rel_path.lower().endswith(".pdf") else "general_document"
    sheet = f"{m.group(1)}-{m.group(2)}"
    prefix = m.group(1)
    for pre, disc, doctype in _DISCIPLINE_BY_PREFIX:
        if prefix.startswith(pre):
            return sheet, disc, doctype
    return sheet, "unknown", "general_pdf"


def _sheet_title_from_filename(rel_path: str, sheet_number: str | None) -> str | None:
    """Tokens between the sheet number and a Rev/extension marker, e.g. 'WALL SECTIONS'."""
    stem = Path(rel_path).stem
    if not sheet_number:
        return None
    # Split on the sheet number, take the remainder, strip a trailing Rev token.
    idx = stem.upper().find(sheet_number)
    if idx < 0:
        return None
    rest = stem[idx + len(sheet_number):]
    rest = re.split(r"(?i)\brev\b", rest)[0]
    title = re.sub(r"[-_]+", " ", rest).strip()
    title = re.sub(r"\s+", " ", title)
    return title.upper() or None if title else None


def _doc_type_from_text(rel_path: str, text: str, fallback: str) -> str:
    name = Path(rel_path).name.lower()
    blob = f"{name}\n{text[:2000].lower()}"
    if re.search(r"\brfi\b|request for information", blob):
        return "rfi"
    if "submittal" in blob or "shop drawing" in blob and "specification" not in blob:
        return "submittal"
    if "meeting minutes" in blob or re.search(r"\bminutes\b", name):
        return "meeting_minutes"
    if re.search(r"specification|section \d{4,6}", blob):
        return "specification"
    if re.search(r"\bschedule\b", name):
        return "schedule"
    if re.search(r"budget|cost|invoice|change order|pay application", blob):
        return "cost_document"
    return fallback


def _project_name(lines: list[str], sheet_title: str | None) -> str | None:
    """Best-effort: a long ALL-CAPS title-block line that isn't the sheet title/datum/note."""
    for raw in lines[:60]:
        line = raw.strip()
        if len(line) < 16 or len(line.split()) < 3:
            continue
        if sheet_title and sheet_title in line.upper():
            continue
        if _DATUM_RE.match(line) or _NOTE_RE.match(line) or _SHEET_RE.search(line):
            continue
        letters = [c for c in line if c.isalpha()]
        if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.85:
            return _clip(line)
    return None


def _issue_status(text: str) -> str | None:
    upper = text.upper()
    for status in _ISSUE_STATUSES:
        if status in upper:
            return status
    return None


def _revision(text: str) -> tuple[str | None, str | None, str | None]:
    num = _REV_NUM_RE.search(text)
    number = num.group(1) if num else None
    date = None
    description = None
    # Prefer a revision line that carries both a number and a date.
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        dm = _DATE_RE.search(line)
        if dm and (_REV_NUM_RE.search(line) or re.search(r"\badd(?:endum)?\b", line, re.IGNORECASE)):
            date = f"{int(dm.group(1)):02d}/{int(dm.group(2)):02d}/{dm.group(3)[-2:]}"
            # Description: text after the date token, else after a revision/ADD marker.
            tail = line[dm.end():].strip(" -\t")
            if not tail:
                am = re.search(r"(ADD\s*\d+.*|ADDENDUM.*)", line, re.IGNORECASE)
                tail = am.group(1).strip() if am else ""
            description = _clip(tail) or None
            break
    if date is None:
        dm = _DATE_RE.search(text)
        if dm and number:
            date = f"{int(dm.group(1)):02d}/{int(dm.group(2)):02d}/{dm.group(3)[-2:]}"
    if description is None:
        am = re.search(r"(ADD\s*\d+[^\n]{0,80})", text, re.IGNORECASE)
        if am:
            description = _clip(am.group(1))
    return number, date, description


def _referenced_sheets(text: str, own_sheet: str | None) -> list[str]:
    refs: list[str] = []
    for m in _SHEET_RE.finditer(text):
        ref = f"{m.group(1)}-{m.group(2)}"
        if own_sheet and ref == own_sheet:
            continue
        refs.append(ref)
    return _dedup(refs)


def _datums(lines: list[str]) -> list[str]:
    out: list[str] = []
    for raw in lines:
        line = raw.strip()
        if "=" in line or "SCALE" in line.upper():
            continue  # a drawing scale (e.g. 1/2" = 1'-0") is not an elevation datum
        m = _DATUM_RE.match(line)
        if m:
            label = m.group(1).strip(" .:-")
            out.append(f"{label} {m.group(2)}".strip())
    return _dedup(out)


def _numbered_notes(lines: list[str]) -> list[str]:
    out = [f"{m.group(1)}. {m.group(2).strip()}"
           for raw in lines if (m := _NOTE_RE.match(raw))]
    return _dedup(out)


def _spaces(text: str) -> list[str]:
    out = [f"{m.group(1).strip()} {m.group(2)}" for m in _SPACE_RE.finditer(text)]
    return _dedup(out)


def _coordination_flags(text: str) -> list[str]:
    low = text.lower()
    flags = [flag for kw, flag in _COORD_KEYWORDS if kw in low]
    return _dedup(flags)


def _submittals(text: str) -> list[str]:
    low = text.lower()
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line and any(kw in line.lower() for kw in _SUBMITTAL_KEYWORDS):
            out.append(line)
    if not out and any(kw in low for kw in _SUBMITTAL_KEYWORDS):
        out.append("Submittal / shop-drawing requirements referenced on this sheet.")
    return _dedup(out)


def _pm_followups(flags: list[str], submittals: list[str], refs: list[str]) -> list[str]:
    out: list[str] = []
    if any("structural" in f or "CMU" in f or "footing" in f or "slab" in f for f in flags):
        out.append("structural coordination")
    if any("waterproof" in f or "roof" in f or "vapor" in f for f in flags):
        out.append("waterproofing/roofing interfaces")
    if any("curtain wall" in f or "glazing" in f for f in flags):
        out.append("glazing/storefront coordination")
    if any("ceiling framing" in f or "delegated" in f for f in flags):
        out.append("delegated exterior ceiling shop drawings")
    if submittals:
        out.append("submittal/shop-drawing review")
    if refs:
        out.append("review referenced sheets/details")
    return _dedup(out)


def from_detail(detail: dict[str, Any]) -> SourceAnalysis:
    """Build a :class:`SourceAnalysis` from an indexed source ``detail`` dict. Fail-soft."""
    rel_path = str(detail.get("rel_path") or "")
    ext = (detail.get("file_ext") or "").lower()
    text = str(detail.get("text_excerpt") or "")[: _MAX_ITEM_CHARS * _MAX_SCAN_LINES]
    lines = text.splitlines()[:_MAX_SCAN_LINES]

    sheet_number, discipline, doctype_guess = _sheet_number_from_filename(rel_path)
    # A bare general fallback by extension when no sheet number was found.
    if sheet_number is None:
        doctype_guess = "general_pdf" if ext == "pdf" else "general_document"
    if sheet_number is None:
        # No sheet number: classify purely from filename + text keywords.
        document_type = _doc_type_from_text(rel_path, text, doctype_guess)
    else:
        # A sheet number implies a drawing. Only the FILENAME (not coordination keywords in the
        # body) may reclassify it as a spec/RFI/submittal sheet, so notes that merely *mention*
        # shop drawings don't flip an architectural drawing to "submittal".
        document_type = doctype_guess
        name_upper = Path(rel_path).name.upper()
        if "SPECIFICATION" in name_upper or re.search(r"\bSPEC\b", name_upper):
            document_type = "specification"
        elif "RFI" in name_upper:
            document_type = "rfi"
        elif "SUBMITTAL" in name_upper:
            document_type = "submittal"

    sheet_title = _sheet_title_from_filename(rel_path, sheet_number)
    number, date, description = _revision(text)
    coordination = _coordination_flags(text)
    submittals = _submittals(text)
    refs = _referenced_sheets(text, sheet_number)

    return SourceAnalysis(
        document_type=document_type,
        discipline=discipline,
        sheet_number=sheet_number,
        sheet_title=sheet_title,
        project_name=_project_name(lines, sheet_title),
        issue_status=_issue_status(text),
        revision_number=number,
        revision_date=date,
        revision_description=description,
        scale=(_SCALE_RE.search(text).group(0) if _SCALE_RE.search(text) else None),
        spaces=_spaces(text),
        datums=_datums(lines),
        numbered_notes=_numbered_notes(lines),
        referenced_sheets=refs,
        submittal_requirements=submittals,
        coordination_flags=coordination,
        pm_followup_categories=_pm_followups(coordination, submittals, refs),
    )
