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
# Procurement / preconstruction document types (NOT drawings — is_drawing stays drawings-only).
BID_DOCUMENT_TYPES = frozenset({"bid_package", "scope_of_work", "procurement_document"})

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

# Bid-package signals + extraction.
_BID_NUM_RE = re.compile(r"bid package\s+(\d{2}-\d{2})\b", re.IGNORECASE)
_BID_NUM_TITLE_RE = re.compile(r"bid package\s+(\d{2}-\d{2})\s+(.+)", re.IGNORECASE)
_BID_BOILERPLATE = "provide all necessary labor"
# Trade keyword -> normalized scope label (storefront/curtain wall/glazing/doors/etc.).
_TRADE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("storefront", "storefront"),
    ("curtain wall", "curtain wall"),
    ("glazing", "glazing"),
    ("window", "windows"),
    ("door", "doors"),
    ("hardware", "hardware"),
    ("break metal", "break metal"),
    ("cladding", "cladding"),
)


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
    # Bid-package / procurement fields (populated only for document_type == "bid_package").
    bid_package_number: str | None = None
    bid_package_title: str | None = None
    inclusions: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    procurement_signals: list[str] = field(default_factory=list)
    trade_scope: list[str] = field(default_factory=list)
    # Generic PM-grade deterministic fields (populated ONLY when explicit/unambiguous; never invented).
    document_number: str | None = None
    title: str | None = None
    vendor: str | None = None
    amount: str | None = None
    doc_date: str | None = None
    doc_status: str | None = None

    @property
    def is_drawing(self) -> bool:
        return self.document_type in DRAWING_DOCUMENT_TYPES

    @property
    def is_bid_package(self) -> bool:
        return self.document_type == "bid_package"

    def to_frontmatter_dict(self) -> dict[str, str]:
        """Scalar fields suitable for card frontmatter; omits None/empty values."""
        out: dict[str, str] = {"document_type": self.document_type}
        if self.discipline and self.discipline != "unknown":
            out["discipline"] = self.discipline
        for key in ("sheet_number", "sheet_title", "issue_status",
                    "revision_number", "revision_date", "revision_description",
                    "bid_package_number", "bid_package_title",
                    "document_number", "title", "vendor", "amount"):
            value = getattr(self, key)
            if value:
                out[key] = str(value)
        # doc_date/doc_status surface under the simpler frontmatter keys date/status.
        if self.doc_date:
            out["date"] = str(self.doc_date)
        if self.doc_status:
            out["status"] = str(self.doc_status)
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


def _bid_package_signal(rel_path: str, text: str) -> bool:
    """Strong bid-package detection from path/filename/text (priority over RFI)."""
    path_low = rel_path.replace("\\", "/").lower()
    blob = f"{Path(rel_path).name.lower()}\n{text[:3000].lower()}"
    if "bid packages" in path_low or "bid package" in blob:
        return True
    if _BID_NUM_RE.search(blob):
        return True
    if "inclusions:" in blob and "exclusions:" in blob:
        return True
    return _BID_BOILERPLATE in blob


def _spreadsheet_doc_type(rel_path: str, text: str) -> str:
    """Narrow high-value Excel classes (else generic 'spreadsheet' → metadata_only).

    Promotion uses near-exact phrases ONLY (never bare 'cost') so generic workbooks do not drift
    into high priority.
    """
    name = Path(rel_path).name.lower()
    blob = f"{name}\n{text[:2000].lower()}"
    # Master/standard cost-code & reference list workbooks are reference metadata, never high-value.
    if _REFERENCE_RE.search(blob):
        return "reference_document"
    if re.search(r"pay app|payapp|payment application|application for payment", blob):
        return "pay_application"
    if re.search(r"\bcost report\b|cost to complete|\bctc\b", blob):
        return "cost_report"
    if re.search(r"cost entries|\bforecast\b|\bbudget\b|project controls", blob):
        return "project_controls"
    if re.search(r"\bstaffing\b|\bmanpower\b|\blabor\b", blob):
        return "staffing_report"
    # Generic coordination/communication matrices are informative but NOT high-value workbook classes.
    if re.search(r"communications? matrix|contact matrix", blob):
        return "communications_matrix"
    if re.search(r"coordination matrix", blob):
        return "coordination_matrix"
    return "spreadsheet"


def _doc_type_from_text(rel_path: str, text: str, fallback: str) -> str:
    name = Path(rel_path).name.lower()
    blob = f"{name}\n{text[:2000].lower()}"
    # Master/standard cost-code & reference lists FIRST (else "cost" drifts them into cost_document).
    if _REFERENCE_RE.search(blob):
        return "reference_document"
    # Bid packages BEFORE rfi: a bid doc that merely mentions RFIs must not become an RFI.
    if _bid_package_signal(rel_path, text):
        return "bid_package"
    # Scope-of-work / SOW exhibits (procurement scope) — amount-gated like bid packages.
    if re.search(r"scope of work|\bsow\b", blob) or re.search(r"exhibit\s+[a-z]\b.*scope", name):
        return "scope_of_work"
    # Stricter RFI: require an explicit RFI marker (incl. a numbered "RFI 032"), not a bare substring.
    if re.search(r"request for information|\brfi\s*#|\brfi\s+no\.?|\brfi\s*#?\s*\d|\brfi log\b", blob):
        return "rfi"
    if "submittal" in blob or ("shop drawing" in blob and "specification" not in blob):
        return "submittal"
    # Potential change order (PCO / COR / "change order request") BEFORE executed change_order.
    if re.search(r"\bpco\b|\bcor\b|potential change order|change order request|change event|\bcce\b", blob):
        return "potential_change_order"
    if re.search(r"\bpcco\b|change order|change directive|\bocd\b", blob):
        return "change_order"
    if re.search(r"pay app|payapp|payment application|application for payment|\bg70[23]\b", blob):
        return "pay_application"
    if re.search(r"purchase order|\bp\.?o\.?\s*#|\bpo\s+no\.?|\bpo\s*#?\s*\d{2,}", blob):
        return "purchase_order"
    # Subcontract BEFORE contract (subcontract is the more specific class).
    if re.search(r"\bsubcontract\b", name):
        return "subcontract"
    if re.search(r"\bcontract\b|notice to proceed|\bntp\b", name):
        return "contract"
    if re.search(r"daily log|daily report", blob):
        return "daily_log"
    if re.search(r"\bmanpower\b|man[- ]?power|man[- ]?hours", blob):
        return "manpower_log"
    if re.search(r"punch ?list", blob):
        return "punch_list"
    # Operations & maintenance and warranty split out of the generic closeout bucket.
    if re.search(r"o\s*&\s*m\b|\bo and m\b|operations?\s*(?:and|&)\s*maintenance", blob):
        return "operations_maintenance"
    if re.search(r"\bwarranty\b|\bwarranties\b", blob):
        return "warranty"
    if re.search(r"close ?out|as[- ]?built", blob):
        return "closeout"
    if "meeting minutes" in blob or re.search(r"\bminutes\b", name):
        return "meeting_minutes"
    if re.search(r"specification|section \d{4,6}", blob):
        return "specification"
    if re.search(r"\bcost report\b", blob):
        return "cost_report"
    if re.search(r"project controls|cost forecast", blob):
        return "project_controls"
    # Strong construction-schedule signal only (bare "schedule" over-matched discussion/agenda docs).
    if _STRONG_SCHEDULE_RE.search(blob):
        return "schedule"
    # Safety BEFORE quality BEFORE inspection (so "Safety Inspection" → safety).
    if re.search(r"\bsafety\b|toolbox talk|\bjha\b|\bjsa\b|\bswms\b", blob):
        return "safety"
    if re.search(r"\bquality\b|\bqa/qc\b|\bqaqc\b|\bncr\b|non[- ]?conformance", blob):
        return "quality"
    if re.search(r"\binspection\b|\binspect\b", blob):
        return "inspection"
    # Generic drawing by filename signal (sheet tokens without a dash, or plan/elevation/section).
    if re.search(r"\bfloor plan\b|\belevation\b|\bbuilding section\b|\bdrawing set\b|\bdetail sheet\b", blob) \
            or re.search(r"\b[A-Z]{1,2}\d{2,3}\b", Path(rel_path).stem.upper()):
        return "drawing"
    if re.search(r"presentation|\bdeck\b", blob):
        return "presentation"
    if re.search(r"marketing|brochure", blob):
        return "marketing"
    if re.search(r"site map|parcel map|project map|vicinity map", blob):
        return "site_map"
    if re.search(r"budget|cost|invoice|pay application", blob):
        return "cost_document"
    return fallback


def _bid_package_number_title(rel_path: str, text: str) -> tuple[str | None, str | None]:
    """Extract (number, title) from `Bid Package 08-03 Glass Windows and Doors` (filename, then text)."""
    for source in (Path(rel_path).stem, text[:1000]):
        m = _BID_NUM_TITLE_RE.search(source)
        if m:
            number = m.group(1)
            title = re.split(r"(?i)\b(inclusions|exclusions|provide all)\b", m.group(2))[0]
            title = re.sub(r"(?i)\.(docx|pdf|doc|txt)$", "", title.strip())
            title = re.sub(r"\s+", " ", title).strip(" -")
            return number, (_clip(title) or None)
        m2 = _BID_NUM_RE.search(source)
        if m2:
            return m2.group(1), None
    return None, None


def _extract_section_lines(text: str, heading: str) -> list[str]:
    """Bounded non-empty lines after a `Heading:` line, until a blank line or the next heading."""
    out: list[str] = []
    capturing = False
    for raw in text.splitlines():
        line = raw.strip()
        low = line.lower()
        if not capturing:
            if low.startswith(heading.lower() + ":") or low == heading.lower():
                capturing = True
                after = line.split(":", 1)[1].strip() if ":" in line else ""
                if after:
                    out.append(after)
            continue
        if not line:
            if out:
                break
            continue
        # Stop at the next short `Word:` heading (e.g. an Exclusions: that follows Inclusions:).
        if low.endswith(":") and len(line) < 40:
            break
        out.append(re.sub(r"^[-*•\s]+", "", line).strip())
        if len(out) >= _MAX_ITEMS:
            break
    return _dedup(out)


def _trade_scope(text: str) -> list[str]:
    low = text.lower()
    return _dedup([label for kw, label in _TRADE_KEYWORDS if kw in low])


def _procurement_signals(rel_path: str) -> list[str]:
    low = rel_path.replace("\\", "/").lower()
    out: list[str] = []
    if "preconstruction" in low:
        out.append("preconstruction")
    if "estimating" in low:
        out.append("estimating")
    if "bid package" in low or "bid packages" in low:
        out.append("bid package")
    if "/commercial/" in low:
        out.append("commercial trade package")
    if "procurement" in low:
        out.append("procurement")
    return _dedup(out)


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


def _classify_non_spreadsheet(rel_path: str, text: str, sheet_number: str | None,
                              doctype_guess: str) -> str:
    """document_type for non-spreadsheet sources (drawing sheet vs filename/text keywords)."""
    if sheet_number is None:
        return _doc_type_from_text(rel_path, text, doctype_guess)
    # A sheet number implies a drawing. Only the FILENAME (not body coordination keywords) may
    # reclassify it as a spec/RFI/submittal/bid sheet.
    name_upper = Path(rel_path).name.upper()
    if "BID PACKAGE" in name_upper:
        return "bid_package"
    if "SPECIFICATION" in name_upper or re.search(r"\bSPEC\b", name_upper):
        return "specification"
    if "RFI" in name_upper:
        return "rfi"
    if "SUBMITTAL" in name_upper:
        return "submittal"
    return doctype_guess


_DOCNUM_RE: dict[str, "re.Pattern[str]"] = {
    "rfi": re.compile(r"(?i)\brfi\s*#?\s*(\d{1,5})"),
    "change_order": re.compile(r"(?i)\b(?:pcco|co)\s*#?\s*(\d{1,5})"),
    "potential_change_order": re.compile(r"(?i)\b(?:pco|cor)\s*#?\s*(\d{1,5})"),
    "pay_application": re.compile(r"(?i)\bpay\s*app(?:lication)?\s*#?\s*(\d{1,4})"),
    "purchase_order": re.compile(r"(?i)\b(?:purchase order|po|p\.o\.)\s*#?\s*(\d{2,8})"),
    "submittal": re.compile(r"(?i)\bsubmittal\s*#?\s*(\d{2}(?:[ ]?\d{2}){1,3}|\d{1,5})"),
}
_ISO_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_AMOUNT_VALUE_RE = re.compile(r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?")
# Trailing " - <Name>" segment is treated as the counterparty for these classes.
_VENDOR_TYPES = {"subcontract", "contract", "purchase_order", "pay_application"}

# --- Tightened deterministic extraction (Phase 8) -------------------------------------------------
# Canonical PM status words. Status is extracted ONLY from a labeled body field or a discrete
# filename segment — never a bare keyword scan (which mistook dropdown lists/instructions for status).
_STATUS_WORDS = (
    "approved as noted", "revise and resubmit", "for review", "in review", "approved",
    "executed", "rejected", "voided", "void", "superseded", "submitted", "issued",
    "draft", "open", "closed", "pending",
)
_STATUS_LABEL_RE = re.compile(r"(?i)\b(?:submittal\s+)?status\s*[:\-]\s*([A-Za-z][A-Za-z /]{2,40})")
# Reject status read out of a dropdown/instruction/example/template context.
_STATUS_REJECT_CTX = re.compile(
    r"(?i)(select|option|dropdown|choose|mark one|for template use|example|e\.g\.|sample|legend)")
# Amounts: explicit "$" value, but never an example/template/placeholder/sample/$0.00/range value.
_AMOUNT_REJECT_CTX = re.compile(r"(?i)(example|e\.g\.|template|placeholder|sample)")
# Labeled date in the body (filename ISO is handled separately). Drops the old unlabeled body-ISO scan.
_DATE_LABEL_RE = re.compile(
    r"(?i)\b(?:date|dated|issued)\s*[:\-]\s*(20\d{2}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})")
# Template / blank / sample / form documents — detected from the FILENAME only (body "sample"/
# "example" is far too noisy in real specs/submittals). Checked with HIGH precedence in from_detail.
_TEMPLATE_FORM_RE = re.compile(
    r"(?i)\btemplate\b|\bblank\b|\bsample\b|\bexample\b|cover sheet|sign[- ]?off form|"
    r"checklist template|cover template")

# --- Phase 10A taxonomy ---------------------------------------------------------------------------
# Binary CAD/BIM drawing files (no text extraction) — always classify as a drawing metadata card.
_CAD_EXTS = frozenset({"dwg", "dxf", "dwf", "rvt", "rfa", "skp", "nwd", "nwc", "ifc"})
# Native scheduling files — always classify as a schedule.
_SCHEDULE_EXTS = frozenset({"xer", "mpp", "mpx"})
# Workbook extensions handled by the spreadsheet classifier.
_SPREADSHEET_EXTS = frozenset({"xlsx", "xlsm", "xls", "xlsb"})
# A STRONG construction-schedule signal (used for PDFs/docs). Bare "schedule" is NOT enough — that
# over-matched "Schedule Discussion"/"Schedule Question". Matches glued forms (constructionschedule).
_STRONG_SCHEDULE_RE = re.compile(
    r"(?i)construction\s*schedule|baseline\s*schedule|project\s*schedule|schedule\s*update|"
    r"schedule\s*narrative|look\s?ahead|3[- ]?week|critical path|\bcpm\b|\bgantt\b|primavera|\bp6\b")
# Master/standard cost-code & reference list files — reference metadata, NOT a project cost instrument.
_REFERENCE_RE = re.compile(
    r"(?i)master cost codes?|cost code master|standard cost codes?|chart of accounts|"
    r"cost code (?:list|library)|\bmaster codes\b")
# Strong, type-appropriate amount labels. For money document types, an amount is extracted ONLY when
# tied to one of these labels — a bare "$" (e.g. "$1", "$42.00") in a scope/bid doc is not enough.
_AMOUNT_STRONG_LABEL_RE = re.compile(
    r"(?i)(?:contract amount|subcontract amount|purchase order amount|po amount|"
    r"change order amount|pcco amount|pco amount|proposal amount|bid amount|total bid|"
    r"total proposal|total amount|schedule of values total|application amount|"
    r"current payment due|retainage|allowance|alternate|contract sum|grand total)"
    r"\s*[:#]?\s*(?:of\s+)?(\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?)")
# Document types whose amounts must be strong-label-gated (scope/bid stray $ values are suppressed).
_LABEL_REQUIRED_AMOUNT_TYPES = frozenset({
    "bid_package", "scope_of_work", "procurement_document", "subcontract", "contract",
    "purchase_order", "change_order", "potential_change_order", "pay_application",
    "cost_report", "project_controls",
})
# Evidence that a "submittal cover/transmittal" is an ACTUAL submittal, not a blank cover template.
_SUBMITTAL_EVIDENCE_RE = re.compile(
    r"(?i)submittal\s*#?\s*\d|\bspec(?:ification)?\s*section|\b\d{6}\b|\b\d{2} \d{2} \d{2}\b|"
    r"package\s*\d")


def _is_template_form(rel_path: str) -> bool:
    """True when the FILENAME marks a blank template/form/sample (not a live instrument)."""
    return bool(_TEMPLATE_FORM_RE.search(Path(rel_path).name))


def _is_blank_submittal_cover(rel_path: str, text: str) -> bool:
    """A submittal COVER/TRANSMITTAL with no actual submittal number/spec/package evidence."""
    name = Path(rel_path).name.lower()
    if "submittal" not in name or not re.search(r"cover|transmittal", name):
        return False
    blob = f"{name}\n{text[:2000].lower()}"
    return not _SUBMITTAL_EVIDENCE_RE.search(blob)


def _extract_labeled_amount(text: str) -> str | None:
    """A "$" amount only when adjacent to a strong, type-appropriate label; else None."""
    for m in _AMOUNT_STRONG_LABEL_RE.finditer(text):
        raw = re.sub(r"\s+", "", m.group(1))
        if raw in ("$0", "$0.00"):
            continue
        before = text[max(0, m.start() - 30):m.start()]
        if _AMOUNT_REJECT_CTX.search(before):
            continue
        return raw
    return None


def _extract_status(segments: list[str], blob: str) -> str | None:
    """Status only from a discrete filename segment or a labeled body field; else None."""
    for seg in segments:
        low = seg.strip().lower()
        if low in _STATUS_WORDS:
            return low
    for m in _STATUS_LABEL_RE.finditer(blob):
        val = re.sub(r"\s+", " ", m.group(1)).strip().lower()
        if "/" in val:
            continue  # a dropdown list of options, not a single resolved status
        window = blob[max(0, m.start() - 40):m.end() + 40]
        if _STATUS_REJECT_CTX.search(window):
            continue
        for word in _STATUS_WORDS:
            if val == word or val.startswith(word + " ") or val.startswith(word):
                return word
    return None


def _extract_amount(text: str) -> str | None:
    """Explicit "$" amount; reject example/template/placeholder/sample context, $0.00, and ranges."""
    for m in _AMOUNT_VALUE_RE.finditer(text):
        raw = re.sub(r"\s+", "", m.group(0))
        if raw in ("$0", "$0.00"):
            continue
        before = text[max(0, m.start() - 30):m.start()]
        if _AMOUNT_REJECT_CTX.search(before):
            continue
        if before.rstrip().endswith(("-", "–")):  # right side of a "$x - $y" range
            continue
        if re.match(r"\s*[-–]\s*\$", text[m.end():m.end() + 40]):  # left side of a range
            continue
        return raw
    return None


def _extract_doc_date(stem: str, text: str) -> str | None:
    """Filename ISO date, else a labeled body date; no unlabeled body-ISO fallback."""
    m = _ISO_DATE_RE.search(stem)
    if m:
        return m.group(1)
    lm = _DATE_LABEL_RE.search(text)
    if lm:
        return lm.group(1)
    return None


def _pm_document_fields(rel_path: str, text: str, document_type: str) -> dict[str, str | None]:
    """Deterministic PM fields from filename/excerpt ONLY — never invented, never from an LLM.

    Returns document_number/title/vendor/amount/doc_date/doc_status (each None when not explicit).
    Status/amount are suppressed for template_form (a blank form is not status/cost evidence).
    """
    stem = Path(rel_path).stem
    blob = f"{stem}\n{text[:2000]}"
    is_template = document_type == "template_form"
    out: dict[str, str | None] = {
        "document_number": None, "title": None, "vendor": None,
        "amount": None, "doc_date": None, "doc_status": None,
    }
    pat = _DOCNUM_RE.get(document_type)
    if pat is not None:
        m = pat.search(blob)
        if m:
            out["document_number"] = re.sub(r"\s+", " ", m.group(1)).strip()
    segs = [s.strip() for s in re.split(r"\s[-–]\s", stem) if s.strip()]
    out["doc_status"] = None if is_template else _extract_status(segs, blob)
    # Trailing " - <text>" segment → vendor (procurement/contract/pay) or title — never a status word.
    trailing = segs[-1] if len(segs) >= 2 else None
    if trailing and trailing.lower() in _STATUS_WORDS:
        trailing = segs[-2] if len(segs) >= 3 else None  # the status segment is not the title
    if trailing and not _ISO_DATE_RE.search(trailing) and trailing.lower() not in _STATUS_WORDS:
        if document_type in _VENDOR_TYPES:
            out["vendor"] = _clip(trailing)
        else:
            out["title"] = _clip(trailing)
    out["doc_date"] = _extract_doc_date(stem, text[:2000])
    # Amount: suppressed for templates; strong-label-gated for money docs (scope/bid stray $ ignored);
    # otherwise an explicit "$" value.
    amount_blob = f"{stem}\n{text[:4000]}"
    if is_template:
        out["amount"] = None
    elif document_type in _LABEL_REQUIRED_AMOUNT_TYPES:
        out["amount"] = _extract_labeled_amount(amount_blob)
    else:
        out["amount"] = _extract_amount(text[:4000])
    return out


def from_detail(detail: dict[str, Any]) -> SourceAnalysis:
    """Build a :class:`SourceAnalysis` from an indexed source ``detail`` dict. Fail-soft."""
    rel_path = str(detail.get("rel_path") or "")
    ext = (detail.get("file_ext") or "").lower()
    text = str(detail.get("text_excerpt") or "")[: _MAX_ITEM_CHARS * _MAX_SCAN_LINES]
    lines = text.splitlines()[:_MAX_SCAN_LINES]

    if ext in _SPREADSHEET_EXTS:
        # Spreadsheets never imply a drawing sheet number; classify by narrow Excel phrases.
        sheet_number, discipline = None, "unknown"
        document_type = _spreadsheet_doc_type(rel_path, text)
    else:
        sheet_number, discipline, doctype_guess = _sheet_number_from_filename(rel_path)
        # A bare general fallback by extension when no sheet number was found.
        if sheet_number is None:
            doctype_guess = "general_pdf" if ext == "pdf" else "general_document"
        document_type = _classify_non_spreadsheet(rel_path, text, sheet_number, doctype_guess)

    # Phase 10A extension precedence: native scheduling files → schedule; binary CAD/BIM → drawing
    # (CAD wins over a schedule keyword in the name, e.g. "M301 Mechanical Schedule.dwg" → drawing).
    if ext in _SCHEDULE_EXTS:
        document_type = "schedule"
    if ext in _CAD_EXTS:
        document_type = "drawing"
    # A blank submittal cover/transmittal (no submittal number/spec/package) is a template, not a record.
    if document_type == "submittal" and _is_blank_submittal_cover(rel_path, text):
        document_type = "template_form"
    # Template / blank-form documents take HIGH precedence over every classified type (they are not
    # live instruments): a "Change Order Template" must not be treated as a real change order.
    if _is_template_form(rel_path):
        document_type = "template_form"
    # First-class email (Phase 10E): a saved `.eml` is always an email record, regardless of any
    # subject/body keyword the generic classifier may have matched (wins over template/RFI/etc.).
    if ext == "eml":
        document_type = "email"

    sheet_title = _sheet_title_from_filename(rel_path, sheet_number)
    number, date, description = _revision(text)
    coordination = _coordination_flags(text)
    submittals = _submittals(text)
    refs = _referenced_sheets(text, sheet_number)

    bid_number = bid_title = None
    inclusions: list[str] = []
    exclusions: list[str] = []
    procurement: list[str] = []
    trade: list[str] = []
    if document_type == "bid_package":
        bid_number, bid_title = _bid_package_number_title(rel_path, text)
        inclusions = _extract_section_lines(text, "inclusions")
        exclusions = _extract_section_lines(text, "exclusions")
        procurement = _procurement_signals(rel_path)
        trade = _trade_scope(text)

    pm = _pm_document_fields(rel_path, text, document_type)

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
        bid_package_number=bid_number,
        bid_package_title=bid_title,
        inclusions=inclusions,
        exclusions=exclusions,
        procurement_signals=procurement,
        trade_scope=trade,
        document_number=pm["document_number"],
        title=pm["title"],
        vendor=pm["vendor"],
        amount=pm["amount"],
        doc_date=pm["doc_date"],
        doc_status=pm["doc_status"],
    )
