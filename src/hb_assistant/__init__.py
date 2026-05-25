"""HB Personal Assistant + Work Product Intelligence System.

Bobby-only local-first MVP.
"""

__version__ = "1.3.0"

from . import links, obsidian, retrieval, store  # Phase 5 + 8 + 11

__all__ = ["__version__", "store", "links", "obsidian", "retrieval"]
