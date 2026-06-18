"""Controlled, operator-facing forecast workflow orchestration (Phase 9+).

This package is the orchestration layer ABOVE ``context/`` (Phase 6 controlled context-generation
runner), ``analysis/`` (Phase 7 controlled analysis runner), and ``common/`` (Phase 8 explicit
package resolution). Modules here compose those proven, default-off building blocks into a single
explicit operation; they add no schema, no DB resolver, and change no production default.
"""
