"""Apple MCC evidence JSON schema validators (apple_mcc_schema_v1).

Bound by measured SHA-256 of this file after WP-00 commit.
"""

from __future__ import annotations

import re
from typing import Any, Callable

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA1_40_RE = re.compile(r"^[0-9a-f]{40}$")
ISO_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

SchemaError = type("SchemaError", (Exception,), {})


def _req(obj: dict[str, Any], key: str) -> Any:
    if key not in obj:
        raise SchemaError(f"missing_field:{key}")
    return obj[key]


def _str(obj: dict[str, Any], key: str) -> str:
    v = _req(obj, key)
    if not isinstance(v, str):
        raise SchemaError(f"type:{key}:expected_str")
    return v


def _int(obj: dict[str, Any], key: str) -> int:
    v = _req(obj, key)
    if not isinstance(v, int) or isinstance(v, bool):
        raise SchemaError(f"type:{key}:expected_int")
    return v


def _bool(obj: dict[str, Any], key: str) -> bool:
    v = _req(obj, key)
    if not isinstance(v, bool):
        raise SchemaError(f"type:{key}:expected_bool")
    return v


def _list(obj: dict[str, Any], key: str) -> list[Any]:
    v = _req(obj, key)
    if not isinstance(v, list):
        raise SchemaError(f"type:{key}:expected_list")
    return v


def _null(obj: dict[str, Any], key: str) -> None:
    v = _req(obj, key)
    if v is not None:
        raise SchemaError(f"type:{key}:expected_null")
    return None


def _enum(val: str, allowed: set[str], key: str) -> str:
    if val not in allowed:
        raise SchemaError(f"enum:{key}:{val}")
    return val


class PredicateFail(Exception):
    """Schema structure OK but pass predicate failed (exit 3)."""


def validate_variable_resolution(obj: dict[str, Any]) -> None:
    if not isinstance(obj, dict):
        raise SchemaError("type:root:expected_object")
    if _str(obj, "schema_version") != "apple_mcc_variable_resolution_v1":
        raise SchemaError("schema_version")
    stage = _enum(_str(obj, "stage"), {"pre_merge", "post_merge"}, "stage")
    for k in ("candidate_sha", "local_sha", "remote_sha", "merge_sha", "base_sha", "tree_sha"):
        v = _str(obj, k)
        if not SHA1_40_RE.match(v):
            raise SchemaError(f"sha40:{k}")
    _enum(_str(obj, "merge_sha_stage"), {"pre_merge_origin_main", "post_merge_origin_main"}, "merge_sha_stage")
    if _str(obj, "branch") != "feat/apple-local-mcc-capture":
        raise PredicateFail("branch")
    pr = _int(obj, "pr_number")
    if pr <= 0:
        raise PredicateFail("pr_number")
    logins = _list(obj, "independent_reviewer_logins")
    if not logins or not all(isinstance(x, str) and x for x in logins):
        raise PredicateFail("independent_reviewer_logins")
    dig = _str(obj, "schemas_module_sha256")
    if not SHA256_RE.match(dig):
        raise SchemaError("schemas_module_sha256")
    if _int(obj, "schemas_module_bytes") <= 0:
        raise PredicateFail("schemas_module_bytes")
    _ = stage


def validate_wp_receipt(obj: dict[str, Any]) -> None:
    if not isinstance(obj, dict):
        raise SchemaError("type:root:expected_object")
    if _str(obj, "schema_version") != "apple_mcc_wp_receipt_v1":
        raise SchemaError("schema_version")
    wp = _str(obj, "wp")
    nn = _str(obj, "nn")
    allowed_wp = {"REG"} | {f"WP-{i:02d}" for i in range(0, 12)}
    allowed_nn = {"reg"} | {f"{i:02d}" for i in range(0, 12)}
    if wp not in allowed_wp:
        raise SchemaError("wp")
    if nn not in allowed_nn:
        raise SchemaError("nn")
    for k in ("start_sha", "end_sha", "base_sha"):
        if not SHA1_40_RE.match(_str(obj, k)):
            raise SchemaError(f"sha40:{k}")
    argv = _list(obj, "tests_argv")
    if not argv or not all(isinstance(x, str) for x in argv):
        raise PredicateFail("tests_argv")
    if _int(obj, "tests_exit_code") != 0:
        raise PredicateFail("tests_exit_code")
    for k in ("files_declared", "files_touched"):
        arr = _list(obj, k)
        if not all(isinstance(x, str) for x in arr):
            raise SchemaError(k)
    _null(obj, "receipt_git_commit")
    utc = _str(obj, "produced_utc")
    if not ISO_Z_RE.match(utc):
        raise SchemaError("produced_utc")


def validate_wp_rollback_receipt(obj: dict[str, Any]) -> None:
    if not isinstance(obj, dict):
        raise SchemaError("type:root:expected_object")
    if _str(obj, "schema_version") != "apple_mcc_wp_rollback_receipt_v1":
        raise SchemaError("schema_version")
    _str(obj, "nn")
    for k in ("pre_rollback_head", "start_sha", "resulting_head"):
        if not SHA1_40_RE.match(_str(obj, k)):
            raise SchemaError(f"sha40:{k}")
    if _str(obj, "resulting_head") != _str(obj, "start_sha"):
        raise PredicateFail("resulting_head")
    rc = _str(obj, "restore_command")
    if not rc.startswith("git reset --hard "):
        raise PredicateFail("restore_command")
    for k in ("files_restored", "unrelated_paths_changed", "before_unrelated_inventory", "after_unrelated_inventory"):
        arr = _list(obj, k)
        if not all(isinstance(x, str) for x in arr):
            raise SchemaError(k)
    if _list(obj, "unrelated_paths_changed"):
        raise PredicateFail("unrelated_paths_changed")
    if _list(obj, "before_unrelated_inventory") != _list(obj, "after_unrelated_inventory"):
        raise PredicateFail("unrelated_inventory_drift")
    if _int(obj, "verify_exit_code") != 0:
        raise PredicateFail("verify_exit_code")


def validate_historical_empty(obj: dict[str, Any]) -> None:
    if not isinstance(obj, dict):
        raise SchemaError("type:root:expected_object")
    if _str(obj, "schema_version") != "apple_mcc_historical_empty_v1":
        raise SchemaError("schema_version")
    if _int(obj, "fabricated_bodies") != 0:
        raise PredicateFail("fabricated_bodies")
    rows = _list(obj, "rows")
    for row in rows:
        if not isinstance(row, dict):
            raise SchemaError("rows_item")
        d = row.get("disposition")
        if d not in {"confirmed_empty", "retried", "unknown", "out_of_scope"}:
            raise SchemaError("disposition")


def validate_live_pilot(obj: dict[str, Any]) -> None:
    if not isinstance(obj, dict):
        raise SchemaError("type:root:expected_object")
    if _str(obj, "schema_version") != "apple_mcc_live_pilot_v1":
        raise SchemaError("schema_version")
    if _bool(obj, "source_mutation") is not False:
        raise PredicateFail("source_mutation")
    if _bool(obj, "redacted") is not True:
        raise PredicateFail("redacted")


def validate_db_copy_rehearsal(obj: dict[str, Any]) -> None:
    if not isinstance(obj, dict):
        raise SchemaError("type:root:expected_object")
    if _str(obj, "schema_version") != "apple_mcc_db_copy_rehearsal_v1":
        raise SchemaError("schema_version")
    if not _str(obj, "source_db_path") or not _str(obj, "copy_db_path"):
        raise PredicateFail("paths")
    if _bool(obj, "copy_ok") is not True:
        raise PredicateFail("copy_ok")
    if _int(obj, "schema_version_before") < 129:
        raise PredicateFail("schema_version_before")
    if _int(obj, "schema_version_after") != 135:
        raise PredicateFail("schema_version_after")
    if _int(obj, "foreign_key_check_rows") != 0:
        raise PredicateFail("foreign_key_check_rows")
    if _str(obj, "integrity_check") != "ok":
        raise PredicateFail("integrity_check")
    if _bool(obj, "wrote_production") is not False:
        raise PredicateFail("wrote_production")


def validate_runbook_checklist(obj: dict[str, Any]) -> None:
    if not isinstance(obj, dict):
        raise SchemaError("type:root:expected_object")
    if _str(obj, "schema_version") != "apple_mcc_runbook_checklist_v1":
        raise SchemaError("schema_version")
    for k in ("operations_doc_present", "pilot_doc_present", "triage_doc_present", "all_cli_dry_run_ok"):
        if _bool(obj, k) is not True:
            raise PredicateFail(k)
    items = _list(obj, "items")
    for it in items:
        if not isinstance(it, dict) or "id" not in it or "ok" not in it:
            raise SchemaError("items")
        if it["ok"] is not True:
            raise PredicateFail(f"item:{it.get('id')}")


def validate_tf_last_created(obj: dict[str, Any]) -> None:
    if not isinstance(obj, dict):
        raise SchemaError("type:root:expected_object")
    if _str(obj, "schema_version") != "apple_mcc_tf_last_created_v1":
        raise SchemaError("schema_version")
    if not _str(obj, "triage_id"):
        raise PredicateFail("triage_id")
    if _int(obj, "github_issue_number") <= 0:
        raise PredicateFail("github_issue_number")
    url = _str(obj, "github_issue_url")
    if "github.com/RMF112018/hb-personal-assistant/issues/" not in url:
        raise PredicateFail("github_issue_url")
    if not SHA1_40_RE.match(_str(obj, "base_sha")):
        raise SchemaError("base_sha")
    if not SHA1_40_RE.match(_str(obj, "candidate_sha")):
        raise SchemaError("candidate_sha")
    if not _str(obj, "reproduction_command") or not _str(obj, "reproduction_evidence_path"):
        raise PredicateFail("reproduction")
    _bool(obj, "unresolved")


def validate_tf_validate_result(obj: dict[str, Any]) -> None:
    if not isinstance(obj, dict):
        raise SchemaError("type:root:expected_object")
    if _str(obj, "schema_version") != "apple_mcc_tf_validate_result_v1":
        raise SchemaError("schema_version")
    if not SHA1_40_RE.match(_str(obj, "candidate_sha")):
        raise SchemaError("candidate_sha")
    if _int(obj, "open_unresolved_count") != 0:
        raise PredicateFail("open_unresolved_count")
    nums = _list(obj, "checked_issue_numbers")
    if not all(isinstance(x, int) and not isinstance(x, bool) for x in nums):
        raise SchemaError("checked_issue_numbers")
    _bool(obj, "canonical_triage_present")
    if _bool(obj, "zero_unresolved") is not True:
        raise PredicateFail("zero_unresolved")
    if _int(obj, "validator_exit_code") != 0:
        raise PredicateFail("validator_exit_code")


def validate_candidate_evidence_index(obj: dict[str, Any]) -> None:
    """Two-level index: members list peers only; self hash lives in sibling index.sha256."""
    if not isinstance(obj, dict):
        raise SchemaError("type:root:expected_object")
    if _str(obj, "schema_version") != "apple_mcc_candidate_evidence_index_v1":
        raise SchemaError("schema_version")
    if not SHA1_40_RE.match(_str(obj, "candidate_sha")):
        raise SchemaError("candidate_sha")
    if not ISO_Z_RE.match(_str(obj, "produced_utc")):
        raise SchemaError("produced_utc")
    members = _list(obj, "members")
    for m in members:
        if not isinstance(m, dict):
            raise SchemaError("member")
        path = m.get("path")
        if not isinstance(path, str) or not path:
            raise SchemaError("member.path")
        # Self must not be a member (F-003 non-self-referential)
        base = path.rsplit("/", 1)[-1]
        if base in {"candidate-evidence-index.json", "index.sha256"}:
            raise PredicateFail("self_referential_member")
        if not isinstance(m.get("sha256"), str) or not SHA256_RE.match(m["sha256"]):
            raise SchemaError("member.sha256")
        if not isinstance(m.get("bytes"), int) or isinstance(m.get("bytes"), bool) or m["bytes"] < 0:
            raise SchemaError("member.bytes")
        if not isinstance(m.get("required"), bool):
            raise SchemaError("member.required")
    if _bool(obj, "integrated_green_inputs_complete") is not True:
        raise PredicateFail("integrated_green_inputs_complete")


def validate_authorization_binding(obj: dict[str, Any]) -> None:
    if not isinstance(obj, dict):
        raise SchemaError("type:root:expected_object")
    if _str(obj, "auth_schema_version") != "apple_mcc_auth_binding_v1":
        raise SchemaError("auth_schema_version")
    if _int(obj, "plan_bytes") <= 0:
        raise PredicateFail("plan_bytes")
    if not SHA256_RE.match(_str(obj, "plan_sha256")):
        raise SchemaError("plan_sha256")
    if _str(obj, "status") != "ACTIVE":
        raise PredicateFail("status")
    path = _str(obj, "auth_validator_module_path")
    if not path.startswith("/"):
        raise SchemaError("auth_validator_module_path")
    if not SHA256_RE.match(_str(obj, "auth_validator_sha256")):
        raise SchemaError("auth_validator_sha256")
    ver = _str(obj, "auth_validator_version")
    if ver == "unknown" or ver not in {"1.0.0"}:
        raise PredicateFail("auth_validator_version")


def validate_reg_receipt(obj: dict[str, Any]) -> None:
    validate_wp_receipt(obj)
    if obj.get("wp") != "REG" or obj.get("nn") != "reg":
        raise PredicateFail("reg_identity")


SCHEMAS: dict[str, Callable[[dict[str, Any]], None]] = {
    "variable_resolution": validate_variable_resolution,
    "wp_receipt": validate_wp_receipt,
    "wp_rollback_receipt": validate_wp_rollback_receipt,
    "historical_empty": validate_historical_empty,
    "live_pilot": validate_live_pilot,
    "db_copy_rehearsal": validate_db_copy_rehearsal,
    "runbook_checklist": validate_runbook_checklist,
    "tf_last_created": validate_tf_last_created,
    "tf_validate_result": validate_tf_validate_result,
    "candidate_evidence_index": validate_candidate_evidence_index,
    "authorization_binding": validate_authorization_binding,
    "reg_receipt": validate_reg_receipt,
}


def validate(schema_name: str, obj: dict[str, Any]) -> None:
    if schema_name not in SCHEMAS:
        raise SchemaError(f"unknown_schema:{schema_name}")
    SCHEMAS[schema_name](obj)
