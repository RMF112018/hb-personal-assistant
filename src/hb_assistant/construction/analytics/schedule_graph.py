"""Relationship adjacency helpers for schedule quality and diff."""

from __future__ import annotations

from typing import Any


def build_adjacency(relationships: list[dict[str, Any]]) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = {}
    for rel in relationships:
        pred = rel.get("predecessor_activity_id")
        succ = rel.get("successor_activity_id")
        if pred and succ:
            adj.setdefault(str(pred), []).append(str(succ))
    return adj


def orphan_relationship_ids(
    relationships: list[dict[str, Any]], activity_ids: set[str]
) -> list[str]:
    orphans: list[str] = []
    for rel in relationships:
        pred = str(rel.get("predecessor_activity_id", ""))
        succ = str(rel.get("successor_activity_id", ""))
        if pred not in activity_ids or succ not in activity_ids:
            orphans.append(f"{pred}->{succ}")
    return orphans