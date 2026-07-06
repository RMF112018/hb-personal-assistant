"""N8C-6 context-pack repository: persist/read, no silent overwrite, explicit stale marking."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.context_pack_models import ContextPackValidationError
from hb_assistant.obsidian_mcp.context_pack_repository import ContextPackRepository
from hb_assistant.store.migrator import SQLiteMigrator


def _header(pack_id: str = "pk1") -> dict:
    return {"pack_id": pack_id, "pack_type": "enrichment_review", "title": "T",
            "scope_json": "{}", "budget_json": "{}", "status": "built", "created_by": "cli",
            "input_digest": "in", "output_digest": "out", "source_count": 1, "claim_count": 1,
            "receipt_count": 1, "item_count": 2, "truncated": True, "stale_count": 1}


def _items() -> list[dict]:
    return [
        {"item_type": "source_summary", "source_id": "s1", "receipt_id": "r1",
         "result_digest": "rd1", "content_excerpt": "hi", "review_tier": "safe_summary",
         "confidence": 0.9, "token_estimate": 1, "included": 1},
        {"item_type": "claim_candidate", "claim_id": "c1", "source_id": "s1",
         "evidence_excerpt": "ev", "review_tier": "claim_candidate", "included": 0,
         "exclusion_reason": "budget_max_items"},
    ]


@pytest.fixture()
def repo(tmp_path: Path) -> ContextPackRepository:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return ContextPackRepository(db)


def test_persist_and_read_back(repo) -> None:
    repo.persist_pack(_header(), _items(), {"input_digest": "in", "output_digest": "out"})
    pack = repo.get_pack("pk1")
    assert pack["pack_type"] == "enrichment_review"
    assert pack["truncated"] == 1 and pack["stale_count"] == 1
    items = repo.list_items("pk1")
    assert [i["item_type"] for i in items] == ["source_summary", "claim_candidate"]
    assert items[0]["item_order"] == 0 and items[1]["item_order"] == 1
    assert items[1]["included"] == 0 and items[1]["exclusion_reason"] == "budget_max_items"
    assert len(repo.list_receipts("pk1")) == 1
    assert [e["event_type"] for e in repo.list_events("pk1")] == ["built"]


def test_no_silent_overwrite(repo) -> None:
    repo.persist_pack(_header(), _items(), None)
    with pytest.raises(ContextPackValidationError, match="pack_exists"):
        repo.persist_pack(_header(), _items(), None)
    assert repo.count_packs() == 1


def test_mark_pack_stale_explicit(repo) -> None:
    repo.persist_pack(_header(), _items(), None)
    assert repo.mark_pack_stale("pk1", detail="drift") is True
    assert repo.get_pack("pk1")["status"] == "stale"
    assert "marked_stale" in [e["event_type"] for e in repo.list_events("pk1")]
    # missing pack -> False, no crash
    assert repo.mark_pack_stale("nope") is False


def test_list_packs_filtered(repo) -> None:
    repo.persist_pack(_header("pk1"), _items(), None)
    assert len(repo.list_packs(pack_type="enrichment_review")) == 1
    assert repo.list_packs(pack_type="source_review") == []
