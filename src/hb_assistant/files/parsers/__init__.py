"""Bounded parsers (excerpt only, never full content). Phase 10 full matrix."""

from .csv import CSVParser
from .docx import DOCXParser
from .image import ImageParser
from .pdf import PDFParser
from .pptx import PPTXParser
from .txt import TXTParser
from .xlsx import XLSXParser
from .zip import ZIPParser

__all__ = [
    "PDFParser",
    "DOCXParser",
    "XLSXParser",
    "PPTXParser",
    "CSVParser",
    "TXTParser",
    "ImageParser",
    "ZIPParser",
]
