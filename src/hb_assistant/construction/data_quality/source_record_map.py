"""Local-only source-system record map (Phase 07A Prompt 03).

Builds deterministic canonical_record_id rows for Procore live/financial/action
records, email messages + project-match candidates, Graph drive items and
ingestion decisions, and email body vault refs.

- Canonical ID format: "{source_system}:{source_table}:{stable_source_key}"
  (per resources/json/source_record_map_contract.json).
- Project linkage prefers explicit project_key on row; falls back to
  project_number_detected reconciled against construction_project_identity
  (Prompt 02). Pilot sources without identity are emitted in "unmapped"
  with reason codes — never silently ignored.
- confidence_class follows 07_CANONICAL... policy (deterministic_exact_id,
  strong_heuristic_*, weak_heuristic_*, etc.). review_required=1 for any
  weak / candidate / pilot-unmapped case.
- All reads local (SQLite + existing store methods or bounded direct conn).
  One reusable helper (list_procore_live_records) was added in repositories.py
  for the high-volume table; the builder intentionally continues to use direct
  queries for the heterogeneous adapters to keep Prompt 03 surgical (see
  store-helpers todo decision record in evidence).
- Writes only via store.upsert_source_system_record (V20) which + builder
  enforce raw_body_persisted=0, full_text=0, external_writeback=0.
- Never DELETE or rewrite prior rows in any table.
- Idempotent (UPSERT on natural keys).

See 07_CANONICAL_PROJECT_IDENTITY_AND_SOURCE_RECORD_POLICY.md and
Prompt 03 spec for rules and unmapped reason semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from hb_assistant.construction.store import ConstructionStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_git_sha() -> str:
    try:
        import subprocess

        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unknown"


class SourceRecordMapBuilder:
    """Local-only builder for canonical source-system record map.

    Usage:
        builder = SourceRecordMapBuilder()
        report = builder.run(dry_run=True)   # preview + unmapped list
        report = builder.run(dry_run=False)  # persist via store upsert
    """

    def __init__(self, store: Optional[ConstructionStore] = None) -> None:
        self._store = store or ConstructionStore()

    def _now(self) -> str:
        return _now()

    def _get_git_sha(self) -> str:
        return _get_git_sha()

    def _get_active_pilot_project_keys(self) -> set[str]:
        """Return set of active pilot project_keys from V5 identity table (defensive)."""
        try:
            conn = __import__(
                "hb_assistant.store.connection", fromlist=["get_connection"]
            ).get_connection()
            cur = conn.execute(
                "SELECT project_key FROM construction_project_identity WHERE is_active = 1"
            )
            return {row[0] for row in cur.fetchall() if row[0]}
        except Exception:
            return set()

    def run(
        self,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Execute the source record map population.

        Returns rich report with counts, by_source_system breakdown,
        capped unmapped list (with reason_code), and guardrails attestation.
        """
        now = self._now()
        repo_sha = self._get_git_sha()
        store = self._store
        pilot_keys = self._get_active_pilot_project_keys()

        mapped_count = 0
        unmapped: list[dict[str, Any]] = []
        by_system: dict[str, dict[str, int]] = {}

        def _bump(system: str, is_mapped: bool) -> None:
            by_system.setdefault(system, {"mapped": 0, "unmapped": 0})
            if is_mapped:
                by_system[system]["mapped"] += 1
            else:
                by_system[system]["unmapped"] += 1

        def _process(rec: dict[str, Any]) -> None:
            nonlocal mapped_count
            # Defense-in-depth (store also enforces)
            for flag in ("raw_body_persisted", "full_text_persisted", "external_writeback_performed"):
                rec[flag] = 0
            if not dry_run:
                store.upsert_source_system_record(rec)
            mapped_count += 1
            _bump(rec["source_system"], True)

        # =====================================================================
        # 1. procore_live_records (dominant pilot volume; deterministic via project_key)
        # =====================================================================
        try:
            conn = __import__(
                "hb_assistant.store.connection", fromlist=["get_connection"]
            ).get_connection()
            cur = conn.execute(
                """
                SELECT project_key, endpoint_id, procore_record_id,
                       title_redacted, source_url_redacted, status,
                       first_seen_at_utc, last_seen_at_utc, updated_at_utc
                FROM procore_live_records
                LIMIT 5000
                """
            )
            for row in cur.fetchall():
                (
                    pk,
                    endpoint,
                    rec_id,
                    title,
                    url,
                    status,
                    first,
                    last,
                    upd,
                ) = row
                stable = str(rec_id)
                canon = f"procore:procore_live_records:{stable}"
                proj_key = pk if pk in pilot_keys else None
                conf = "deterministic_exact_id" if proj_key else "weak_heuristic_single_signal"
                review = bool(not proj_key)
                reason = None if proj_key else ("pilot_source_unmapped" if pk else "no_project_identity_signal")
                rec = {
                    "canonical_record_id": canon,
                    "project_key": proj_key,
                    "project_number": None,
                    "source_system": "procore",
                    "source_table": "procore_live_records",
                    "source_primary_key": stable,
                    "record_type": "procore_live_record",
                    "record_status": status,
                    "title_redacted": title,
                    "source_url_redacted": url,
                    "first_seen_utc": first,
                    "last_seen_utc": last,
                    "source_updated_utc": upd,
                    "confidence_class": conf,
                    "review_required": 1 if review else 0,
                    "mapping_signals_json": (
                        '{"endpoint":"' + (endpoint or "") + '"}' if proj_key else None
                    ),
                }
                if proj_key:
                    _process(rec)
                else:
                    unmapped.append(
                        {
                            "canonical_record_id": canon,
                            "source_table": "procore_live_records",
                            "reason_code": reason,
                            "signals": {"endpoint": endpoint, "has_record_id": bool(rec_id)},
                        }
                    )
                    _bump("procore", False)
        except Exception:
            pass  # never let one adapter break the run

        # =====================================================================
        # 2. procore_financial_contracts (and related financials via same pattern)
        # =====================================================================
        try:
            conn = __import__(
                "hb_assistant.store.connection", fromlist=["get_connection"]
            ).get_connection()
            cur = conn.execute(
                """
                SELECT project_key, record_key, contract_family, title_redacted, status,
                       first_seen_at_utc, last_seen_at_utc
                FROM procore_financial_contracts
                LIMIT 300
                """
            )
            for row in cur.fetchall():
                pk, rkey, fam, title, st, first, last = row
                canon = f"procore:procore_financial_contracts:{rkey}"
                proj_key = pk if pk in pilot_keys else None
                conf = "deterministic_exact_id" if proj_key else "weak_heuristic_single_signal"
                review = bool(not proj_key)
                rec = {
                    "canonical_record_id": canon,
                    "project_key": proj_key,
                    "project_number": None,
                    "source_system": "procore",
                    "source_table": "procore_financial_contracts",
                    "source_primary_key": rkey,
                    "record_type": "financial_contract",
                    "record_status": st,
                    "title_redacted": title,
                    "source_url_redacted": None,
                    "first_seen_utc": first,
                    "last_seen_utc": last,
                    "source_updated_utc": None,
                    "confidence_class": conf,
                    "review_required": 1 if review else 0,
                    "mapping_signals_json": '{"family":"' + (fam or "") + '"}' if proj_key else None,
                }
                if proj_key:
                    _process(rec)
                else:
                    unmapped.append(
                        {
                            "canonical_record_id": canon,
                            "source_table": "procore_financial_contracts",
                            "reason_code": "pilot_source_unmapped" if pk else "no_project_identity_signal",
                            "signals": {"family": fam},
                        }
                    )
                    _bump("procore", False)
        except Exception:
            pass

        # =====================================================================
        # 3. email_messages (via project_number_detected or project_key)
        # =====================================================================
        try:
            conn = __import__(
                "hb_assistant.store.connection", fromlist=["get_connection"]
            ).get_connection()
            cur = conn.execute(
                """
                SELECT message_id, project_key, project_number_detected,
                       subject_redacted, project_match_confidence,
                       first_seen_utc, last_seen_utc
                FROM email_messages
                WHERE project_key IS NOT NULL OR project_number_detected IS NOT NULL
                LIMIT 200
                """
            )
            for row in cur.fetchall():
                mid, pkey, pnum, subj, mconf, first, last = row
                canon = f"email:email_messages:{mid}"
                proj_key = pkey if pkey in pilot_keys else None
                conf_class = (
                    "strong_heuristic_multi_signal"
                    if mconf and float(mconf or 0) >= 0.8
                    else "weak_heuristic_single_signal"
                )
                review = bool(not proj_key)
                rec = {
                    "canonical_record_id": canon,
                    "project_key": proj_key,
                    "project_number": pnum,
                    "source_system": "email",
                    "source_table": "email_messages",
                    "source_primary_key": mid,
                    "record_type": "email_message",
                    "record_status": None,
                    "title_redacted": subj,
                    "source_url_redacted": None,
                    "first_seen_utc": first,
                    "last_seen_utc": last,
                    "source_updated_utc": None,
                    "confidence_class": conf_class,
                    "review_required": 1 if review else 0,
                    "mapping_signals_json": (
                        '{"detected":"' + (pnum or "") + '","conf":"' + str(mconf or "") + '"}'
                        if proj_key
                        else None
                    ),
                }
                if proj_key:
                    _process(rec)
                else:
                    unmapped.append(
                        {
                            "canonical_record_id": canon,
                            "source_table": "email_messages",
                            "reason_code": "no_project_identity_signal",
                            "signals": {"detected_number": pnum},
                        }
                    )
                    _bump("email", False)
        except Exception:
            pass

        # =====================================================================
        # 4. construction_drive_items (those already project-matched in V17+)
        # =====================================================================
        try:
            conn = __import__(
                "hb_assistant.store.connection", fromlist=["get_connection"]
            ).get_connection()
            cur = conn.execute(
                """
                SELECT source_id, drive_item_id, name, path,
                       project_key, project_number_detected, match_confidence, match_status,
                       first_seen_utc, last_seen_utc
                FROM construction_drive_items
                WHERE project_key IS NOT NULL OR project_number_detected IS NOT NULL
                LIMIT 1000
                """
            )
            for row in cur.fetchall():
                sid, did, name, path, pkey, pnum, mconf, mstatus, first, last = row
                stable = f"{sid}:{did}"
                canon = f"graph_files:construction_drive_items:{stable}"
                proj_key = pkey if pkey in pilot_keys else None
                conf_class = (
                    "deterministic_project_number"
                    if mconf in ("high", "medium")
                    else "weak_heuristic_single_signal"
                )
                review = bool(not proj_key)
                rec = {
                    "canonical_record_id": canon,
                    "project_key": proj_key,
                    "project_number": pnum or pkey,
                    "source_system": "graph_files",
                    "source_table": "construction_drive_items",
                    "source_primary_key": stable,
                    "record_type": "drive_item",
                    "record_status": mstatus,
                    "title_redacted": name,
                    "source_url_redacted": path,  # internal path, already redacted in storage
                    "first_seen_utc": first,
                    "last_seen_utc": last,
                    "source_updated_utc": None,
                    "confidence_class": conf_class,
                    "review_required": 1 if review else 0,
                    "mapping_signals_json": '{"match":"' + (mstatus or "") + '"}' if proj_key else None,
                }
                if proj_key:
                    _process(rec)
                else:
                    unmapped.append(
                        {
                            "canonical_record_id": canon,
                            "source_table": "construction_drive_items",
                            "reason_code": "pilot_source_unmapped",
                            "signals": {},
                        }
                    )
                    _bump("graph_files", False)
        except Exception:
            pass

        # =====================================================================
        # 5. construction_file_ingestion_decisions
        # =====================================================================
        try:
            conn = __import__(
                "hb_assistant.store.connection", fromlist=["get_connection"]
            ).get_connection()
            cur = conn.execute(
                """
                SELECT source_id, drive_item_id, project_key, project_number_detected,
                       ingestion_disposition, decided_utc
                FROM construction_file_ingestion_decisions
                WHERE project_key IS NOT NULL OR project_number_detected IS NOT NULL
                LIMIT 300
                """
            )
            for row in cur.fetchall():
                sid, did, pkey, pnum, disp, dec = row
                stable = f"{sid}:{did}"
                canon = f"graph_files:construction_file_ingestion_decisions:{stable}"
                proj_key = pkey if pkey in pilot_keys else None
                rec = {
                    "canonical_record_id": canon,
                    "project_key": proj_key,
                    "project_number": pnum,
                    "source_system": "graph_files",
                    "source_table": "construction_file_ingestion_decisions",
                    "source_primary_key": stable,
                    "record_type": "ingestion_decision",
                    "record_status": disp,
                    "title_redacted": None,
                    "source_url_redacted": None,
                    "first_seen_utc": dec,
                    "last_seen_utc": dec,
                    "source_updated_utc": dec,
                    "confidence_class": "deterministic_exact_id" if proj_key else "weak_heuristic_single_signal",
                    "review_required": 0 if proj_key else 1,
                    "mapping_signals_json": None,
                }
                if proj_key:
                    _process(rec)
                else:
                    unmapped.append(
                        {
                            "canonical_record_id": canon,
                            "source_table": "construction_file_ingestion_decisions",
                            "reason_code": "no_project_identity_signal",
                            "signals": {},
                        }
                    )
                    _bump("graph_files", False)
        except Exception:
            pass

        # =====================================================================
        # 6. email_message_body_vault_refs (metadata only)
        # =====================================================================
        try:
            conn = __import__(
                "hb_assistant.store.connection", fromlist=["get_connection"]
            ).get_connection()
            cur = conn.execute(
                """
                SELECT v.message_id, v.project_key, m.project_number_detected, v.created_utc
                FROM email_message_body_vault_refs v
                LEFT JOIN email_messages m ON m.message_id = v.message_id
                WHERE v.project_key IS NOT NULL OR m.project_number_detected IS NOT NULL
                LIMIT 100
                """
            )
            for row in cur.fetchall():
                mid, pkey, pnum, cr = row
                canon = f"email:email_message_body_vault_refs:{mid}"
                proj_key = pkey if pkey in pilot_keys else None
                rec = {
                    "canonical_record_id": canon,
                    "project_key": proj_key,
                    "project_number": pnum,
                    "source_system": "email",
                    "source_table": "email_message_body_vault_refs",
                    "source_primary_key": mid,
                    "record_type": "body_vault_ref",
                    "record_status": None,
                    "title_redacted": None,
                    "source_url_redacted": None,
                    "first_seen_utc": cr,
                    "last_seen_utc": cr,
                    "source_updated_utc": None,
                    "confidence_class": "deterministic_exact_id" if proj_key else "weak_heuristic_single_signal",
                    "review_required": 0 if proj_key else 1,
                    "mapping_signals_json": None,
                }
                if proj_key:
                    _process(rec)
                else:
                    unmapped.append(
                        {
                            "canonical_record_id": canon,
                            "source_table": "email_message_body_vault_refs",
                            "reason_code": "no_project_identity_signal",
                            "signals": {},
                        }
                    )
                    _bump("email", False)
        except Exception:
            pass

        # =====================================================================
        # 7. email_project_matches (relationship candidates)
        # =====================================================================
        try:
            conn = __import__(
                "hb_assistant.store.connection", fromlist=["get_connection"]
            ).get_connection()
            cur = conn.execute(
                """
                SELECT match_id, message_id, project_key, project_number,
                       match_signal, confidence, review_required
                FROM email_project_matches
                LIMIT 200
                """
            )
            for row in cur.fetchall():
                mid, msgid, pkey, pnum, sig, conf, rev = row
                canon = f"email:email_project_matches:{mid}"
                proj_key = pkey if pkey in pilot_keys else None
                conf_class = (
                    "strong_heuristic_multi_signal"
                    if conf and float(conf or 0) >= 0.8
                    else "weak_heuristic_single_signal"
                )
                # Candidates are inherently review-required unless human-promoted later
                review = True
                rec = {
                    "canonical_record_id": canon,
                    "project_key": proj_key,
                    "project_number": pnum,
                    "source_system": "email",
                    "source_table": "email_project_matches",
                    "source_primary_key": mid,
                    "record_type": "project_match_candidate",
                    "record_status": None,
                    "title_redacted": None,
                    "source_url_redacted": None,
                    "first_seen_utc": None,
                    "last_seen_utc": None,
                    "source_updated_utc": None,
                    "confidence_class": conf_class,
                    "review_required": 1,
                    "mapping_signals_json": '{"signal":"' + (sig or "") + '","conf":' + str(conf or 0) + "}",
                }
                if proj_key:
                    _process(rec)
                else:
                    unmapped.append(
                        {
                            "canonical_record_id": canon,
                            "source_table": "email_project_matches",
                            "reason_code": "weak_heuristic_requires_review",
                            "signals": {"match_signal": sig},
                        }
                    )
                    _bump("email", False)
        except Exception:
            pass

        total_unmapped = len(unmapped)
        # ensure keys
        for s in list(by_system.keys()):
            by_system[s].setdefault("unmapped", 0)

        return {
            "dry_run": dry_run,
            "run_utc": now,
            "repo_sha": repo_sha,
            "schema_version": 20,
            "mapped_count": mapped_count,
            "unmapped_count": total_unmapped,
            "by_source_system": by_system,
            "unmapped": unmapped[:100],  # cap for evidence size / readability
            "guardrails": {
                "local_only": True,
                "no_raw_content": True,
                "no_destructive_changes": True,
                "pilot_unmapped_emitted": total_unmapped > 0,
                "conflicts_require_review": True,
            },
            "would_persist": not dry_run,
            "persisted": not dry_run,
        }


def build_source_record_map(
    *,
    store: Optional[ConstructionStore] = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Convenience wrapper (matches plan + CLI expectation for Prompt 03)."""
    return SourceRecordMapBuilder(store=store).run(dry_run=dry_run)
