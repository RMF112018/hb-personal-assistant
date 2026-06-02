"""Phase 08A Answer Synthesis Agent (A04) + interactive query (Prompt 08).

Source-linked, research-first interactive Q&A: build a research packet, gate synthesis
through the mock-first Claude adapter, and return an advisory answer with source refs,
claim-strength labels, review tiers, an evaluation preview, warnings, and advisory-vs-
actionable separation. Tier-3 / high-impact items are never presented as final
conclusions. No raw content; answers are not persisted.
"""

from __future__ import annotations

from .agent import build_answer_synthesis_agent_proof, synthesize_answer
from .evaluation import build_evaluation_preview, build_output_evaluation_agent_proof
from .models import EvaluationPreview, QueryResult
from .store import read_latest_evaluation_runs, write_evaluation_run

__all__ = [
    "build_answer_synthesis_agent_proof",
    "synthesize_answer",
    "build_evaluation_preview",
    "build_output_evaluation_agent_proof",
    "EvaluationPreview",
    "QueryResult",
    "read_latest_evaluation_runs",
    "write_evaluation_run",
]
