"""Batch envelope for SSH JSONL transport."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


SCHEMA = "apple_mcc_batch_envelope_v1"


@dataclass
class BatchEnvelope:
    batch_id: str
    capture_run_id: str
    domain: str  # mail | calendar | contacts
    item_count: int
    payload_sha256: str
    created_utc: str
    schema_version: str = SCHEMA
    items: list[dict[str, Any]] = field(default_factory=list)

    def to_json_line(self) -> str:
        body = {
            "schema_version": self.schema_version,
            "batch_id": self.batch_id,
            "capture_run_id": self.capture_run_id,
            "domain": self.domain,
            "item_count": self.item_count,
            "payload_sha256": self.payload_sha256,
            "created_utc": self.created_utc,
            "items": self.items,
        }
        return json.dumps(body, separators=(",", ":"), sort_keys=True)

    @classmethod
    def from_items(
        cls,
        *,
        batch_id: str,
        capture_run_id: str,
        domain: str,
        items: list[dict[str, Any]],
        created_utc: str,
    ) -> BatchEnvelope:
        raw = json.dumps(items, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return cls(
            batch_id=batch_id,
            capture_run_id=capture_run_id,
            domain=domain,
            item_count=len(items),
            payload_sha256=hashlib.sha256(raw).hexdigest(),
            created_utc=created_utc,
            items=items,
        )

    def validate(self) -> None:
        if self.schema_version != SCHEMA:
            raise ValueError("bad_schema")
        if self.domain not in {"mail", "calendar", "contacts"}:
            raise ValueError("bad_domain")
        if self.item_count != len(self.items):
            raise ValueError("item_count_mismatch")
        raw = json.dumps(self.items, separators=(",", ":"), sort_keys=True).encode("utf-8")
        if hashlib.sha256(raw).hexdigest() != self.payload_sha256:
            raise ValueError("payload_sha256_mismatch")
