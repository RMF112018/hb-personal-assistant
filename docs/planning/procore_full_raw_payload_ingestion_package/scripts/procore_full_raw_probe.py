#!/usr/bin/env python3
"""Print Procore full-raw vs legacy-redacted coverage without printing payload bodies."""
from __future__ import annotations
import hashlib, json, sqlite3, sys
from pathlib import Path

def sha12(v: str) -> str:
    return hashlib.sha256(v.encode("utf-8", "replace")).hexdigest()[:12]

def exists(conn, table):
    return conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None

def main():
    if len(sys.argv) != 2:
        print("usage: procore_full_raw_probe.py <sqlite-db>", file=sys.stderr)
        return 2
    db=Path(sys.argv[1])
    conn=sqlite3.connect(db)
    conn.row_factory=sqlite3.Row
    if not exists(conn, "procore_endpoint_raw_payloads"):
        print({"error":"missing procore_endpoint_raw_payloads"})
        return 1
    print("# source_quality_distribution")
    for r in conn.execute("""
      SELECT source_quality, raw_procore_payload_persisted, COUNT(*) rows
      FROM procore_endpoint_raw_payloads
      GROUP BY source_quality, raw_procore_payload_persisted
      ORDER BY source_quality
    """):
        print(dict(r))
    print("# field_name_samples")
    for r in conn.execute("""
      SELECT endpoint_key, source_quality, raw_procore_payload_persisted, payload_json
      FROM procore_endpoint_raw_payloads
      ORDER BY endpoint_key, source_quality LIMIT 50
    """):
        try:
            payload=json.loads(r["payload_json"] or "{}")
        except Exception:
            payload={}
        fields=sorted(map(str,payload.keys()))[:30] if isinstance(payload,dict) else [type(payload).__name__]
        print({"endpoint_key":r["endpoint_key"],"source_quality":r["source_quality"],"raw_procore_payload_persisted":r["raw_procore_payload_persisted"],"payload_hash12":sha12(r["payload_json"] or ""),"field_names":fields})
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
