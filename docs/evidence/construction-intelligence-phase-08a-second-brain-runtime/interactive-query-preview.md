# Phase 08A — Interactive Query Preview (Prompt 08)

Two offline mock-adapter runs against seeded temporary databases, showing the
source-linked, research-first query output. No external calls, no raw content.

## A. Tier-1 source-backed query (synthesized advisory answer)

Question: *"What changed on the pilot project this week?"* (project P1; accepted
relationship + accepted memory seeded). Synthesis proceeds; the answer is advisory and
source-linked, with a passing evaluation preview.

```json
{
  "advisory_vs_actionable_marking": {
    "actionable_recommendations": [],
    "advisory_note": "Advisory intelligence only. High-impact / Tier-3 items are routed to mandatory review and are never presented as final conclusions.",
    "disposition": "advisory"
  },
  "answer_redacted": "[mock advisory synthesis] 2 source reference(s); review tier 1 (T1_DETERMINISTIC_SOURCE_BACKED); advisory only \u2014 verify against linked sources.",
  "confidence_labels": {
    "claim_strength": "strong",
    "overall": "medium",
    "review_reason_code": "T1_DETERMINISTIC_SOURCE_BACKED",
    "review_tier": 1
  },
  "evaluation_summary": {
    "checklist": {
      "advisory_vs_actionable_classified": true,
      "confidence_class_present": true,
      "conflict_warnings_surfaced": true,
      "coverage_warnings_surfaced": true,
      "degradation_mode_set_when_insufficient": true,
      "no_raw_content_in_output": true,
      "no_tier_3_treated_as_accepted_fact": true,
      "review_tiers_assigned": true,
      "source_references_present": true,
      "stale_unknown_warnings_surfaced": true
    },
    "checklist_passed": 10,
    "checklist_total": 10,
    "passed": true,
    "review_status": "auto_advisory",
    "review_tier": 1,
    "score": 1.0
  },
  "mode": "mock",
  "packet_receipt_id": null,
  "research_packet_summary": {
    "context_quality_class": "partial",
    "degradation_mode": "graceful_degraded",
    "open_questions_count": 5,
    "packet_id": "45b3461e1dad2b2f983b3543a2765934",
    "source_coverage": 0.2857,
    "source_ref_count": 2
  },
  "retrieval_receipt_id": null,
  "review_tiers": {
    "distribution": {
      "1": 2,
      "2": 0,
      "3": 0
    },
    "max_tier": 1,
    "review_status": "auto_advisory"
  },
  "source_refs": [
    {
      "confidence_class": "human_promoted",
      "record_ref": "rel-1",
      "record_type": "references",
      "review_tier": "1",
      "source_family": "cross_source_relationships",
      "source_ref": "rel-1"
    },
    {
      "confidence_class": "high",
      "record_ref": "mem1",
      "record_type": "fact",
      "review_tier": "1",
      "source_family": "accepted_long_term_memory",
      "source_ref": "mem1"
    }
  ],
  "synthesized": true,
  "warnings": [
    "no_read_model:meeting_prep_brief_sections",
    "no_read_model:review_controlled_correspondence_context",
    "source_coverage_below_min:0.29<0.5"
  ]
}
```

## B. High-impact / Tier-3 query (gated — not a final conclusion)

Question: *"Is the contractor entitled to this claim?"* (project P1; a review-required,
financial relationship seeded -> Tier 3). The adapter gate refuses synthesis: the answer
is empty, `review_status=review_required`, degradation `blocked`, and warnings surface the
block. The high-impact determination is never presented as a final conclusion.

```json
{
  "advisory_vs_actionable_marking": {
    "actionable_recommendations": [],
    "advisory_note": "Advisory intelligence only. High-impact / Tier-3 items are routed to mandatory review and are never presented as final conclusions.",
    "disposition": "advisory"
  },
  "answer_redacted": "",
  "confidence_labels": {
    "claim_strength": "insufficient",
    "overall": "low",
    "review_reason_code": "T3_MODEL_ONLY",
    "review_tier": 3
  },
  "evaluation_summary": {
    "checklist": {
      "advisory_vs_actionable_classified": true,
      "confidence_class_present": true,
      "conflict_warnings_surfaced": true,
      "coverage_warnings_surfaced": true,
      "degradation_mode_set_when_insufficient": true,
      "no_raw_content_in_output": true,
      "no_tier_3_treated_as_accepted_fact": true,
      "review_tiers_assigned": true,
      "source_references_present": true,
      "stale_unknown_warnings_surfaced": true
    },
    "checklist_passed": 10,
    "checklist_total": 10,
    "passed": true,
    "review_status": "review_required",
    "review_tier": 3,
    "score": 1.0
  },
  "mode": "mock",
  "packet_receipt_id": null,
  "research_packet_summary": {
    "context_quality_class": "partial",
    "degradation_mode": "graceful_degraded",
    "open_questions_count": 7,
    "packet_id": "45b3461e1dad2b2f983b3543a2765934",
    "source_coverage": 0.1429,
    "source_ref_count": 1
  },
  "retrieval_receipt_id": null,
  "review_tiers": {
    "distribution": {
      "1": 0,
      "2": 0,
      "3": 1
    },
    "max_tier": 3,
    "review_status": "review_required"
  },
  "source_refs": [
    {
      "confidence_class": "weak_heuristic",
      "record_ref": "rel-review",
      "record_type": "references",
      "review_tier": "3",
      "source_family": "cross_source_relationships",
      "source_ref": "rel-review"
    }
  ],
  "synthesized": false,
  "warnings": [
    "degradation_mode:blocked",
    "no_read_model:meeting_prep_brief_sections",
    "no_read_model:review_controlled_correspondence_context",
    "synthesis_blocked:context_or_tier_gate",
    "tier_3_density_exceeds_threshold:1.00>0.35",
    "tier_3_mandatory_review"
  ]
}
```

_Generated offline via MockClaudeAdapter; live Claude is never invoked._
