"""Phase 10J — enrichment cross-cutting library: reason taxonomy, observability, safe evidence.

Proves the canonical reject-reason normalizer maps every engine-native reason to the fixed taxonomy,
the observability wrapper counts calls/latency/failures without changing behavior, and the safe report
renderer is whitelist-only (a sensitive string in an unknown key can never leak).
"""

from __future__ import annotations

import json

import pytest

from hb_assistant.construction.classification.client import OllamaUnavailable
from hb_assistant.obsidian_mcp import source_enrichment as enr


@pytest.mark.parametrize("native,canonical", [
    ("format_invalid", "invalid_format"),
    ("noncanonical_shape", "invalid_format"),
    ("invalid_response", "invalid_format"),
    ("invalid_json", "invalid_format"),
    ("empty_response", "model_unavailable"),
    ("ollama_unavailable", "model_unavailable"),
    ("timeout", "model_timeout"),
    ("rejected", "weak_basis"),
    ("missing_source_record", "unsupported_claim"),
    ("metadata_conflict", "metadata_conflict"),
    ("unknown_tag", "unknown_tag"),
    ("unsupported_claim", "unsupported_claim"),
    ("unknown_relationship_type", "unknown_relationship_type"),
    ("duplicate_review_only", "duplicate_review_only"),
    ("ollama:ollama_timeout", "model_timeout"),
    ("ollama:ollama_status_500", "model_unavailable"),
    ("tags:frontmatter_not_block_style", "invalid_format"),
    ("block:ambiguous_existing_block", "invalid_format"),
])
def test_normalize_reason_maps_to_taxonomy(native, canonical):
    assert enr.normalize_reason(native) == canonical
    assert canonical in enr.REJECT_REASONS


def test_normalize_reason_passes_unknown_through_verbatim():
    # An unrecognized reason is preserved (never silently bucketed into a wrong code).
    assert enr.normalize_reason("brand_new_reason") == "brand_new_reason"


def test_merge_reasons_aggregates_by_canonical_code():
    merged = enr.merge_reasons({"rejected": 2, "invalid_json": 1},
                               {"timeout": 1, "format_invalid": 1}, None)
    assert merged == {"invalid_format": 2, "model_timeout": 1, "weak_basis": 2}


class _Inner:
    base_url = "http://localhost:11434"
    model = "qwen2.5:14b"

    def __init__(self, *, exc=None, out="ok"):
        self._exc, self._out = exc, out

    def generate_json(self, *, system, prompt):
        if self._exc:
            raise self._exc
        return self._out

    def generate_text(self, *, system, prompt):
        if self._exc:
            raise self._exc
        return self._out


def test_observable_client_counts_success():
    rec = enr.ObservabilityRecorder()
    client = enr.ObservableClient(_Inner(out='{"tags": []}'), rec)
    assert client.model == "qwen2.5:14b" and client.base_url == "http://localhost:11434"
    client.generate_json(system="s", prompt="p")
    client.generate_text(system="s", prompt="p")
    assert rec.calls == 2 and rec.successes == 2 and rec.failures == 0 and rec.timeouts == 0
    assert len(rec.latencies_ms) == 2
    snap = rec.snapshot(model="qwen2.5:14b", model_match="exact")
    assert snap["ollama_calls"] == 2 and snap["successes"] == 2 and snap["tokens"] is None


def test_observable_client_classifies_timeout_and_reraises():
    rec = enr.ObservabilityRecorder()
    client = enr.ObservableClient(_Inner(exc=OllamaUnavailable("ollama_timeout")), rec)
    with pytest.raises(OllamaUnavailable):
        client.generate_json(system="s", prompt="p")
    assert rec.calls == 1 and rec.failures == 1 and rec.timeouts == 1 and rec.successes == 0
    assert len(rec.latencies_ms) == 1  # latency recorded even on failure


def test_observable_client_non_timeout_failure_not_counted_as_timeout():
    rec = enr.ObservabilityRecorder()
    client = enr.ObservableClient(_Inner(exc=OllamaUnavailable("ollama_status_500")), rec)
    with pytest.raises(OllamaUnavailable):
        client.generate_text(system="s", prompt="p")
    assert rec.failures == 1 and rec.timeouts == 0


def test_render_report_is_count_only_and_leaks_nothing():
    safe = {
        "mode": "dry-run", "model": "qwen2.5:14b", "modes_run": ["tags"],
        "project_number": "23-435-01",
        "tags": {"cards_checked": 3, "tags_proposed": 4, "tags_applied": 2, "cards_tagged": 2,
                 "failed": 1, "SECRET_TAG_KEY": "SENSITIVE-CARD-TITLE"},
        "reject_reasons": {"unknown_tag": 1},
        "observability": {"ollama_calls": 3, "successes": 3, "failures": 0, "timeouts": 0,
                          "latency_ms_total": 30, "latency_ms_avg": 10, "latency_ms_max": 12,
                          "model": "qwen2.5:14b", "model_match": None, "tokens": None},
        "invariants": {"db_mutations": 0, "queue_delta": 0, "created": 0, "deleted": 0},
        "LEAK_KEY": "SENSITIVE-EMAIL-ADDRESS",
    }
    report = enr.render_enrichment_report(safe)
    assert "SENSITIVE-CARD-TITLE" not in report and "SENSITIVE-EMAIL-ADDRESS" not in report
    assert "cards_checked: 3" in report and "applied: 2" in report
    assert "unknown_tag: 1" in report and "ollama_calls: 3" in report


def test_write_enrichment_evidence_two_tier(tmp_path):
    safe = {"mode": "dry-run", "model": "qwen2.5:14b", "modes_run": ["review"],
            "reject_reasons": {}, "observability": {}, "invariants": {}}
    detail = [{"note_id12": "abc123def456", "result": "no_new_tags"}]
    enr.write_enrichment_evidence(tmp_path, safe, detail)
    assert (tmp_path / "phase10j-enrichment-summary-safe.json").is_file()
    assert (tmp_path / "phase10j-enrichment-report-safe.md").is_file()
    ls = tmp_path / "local-sensitive" / "phase10j-enrichment-detail-local-sensitive.json"
    assert ls.is_file()
    assert json.loads(ls.read_text())["rows"] == detail
