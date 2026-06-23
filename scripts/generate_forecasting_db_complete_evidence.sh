#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

LIVE_DB="${LIVE_DB:-/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

# Use the repo venv interpreter (has hb_assistant + deps) rather than a bare system python3, which may
# lack pydantic/etc. Callers (e.g. tests) may override VENV_PYTHON; fall back to python3 if absent.
VENV_PYTHON="${VENV_PYTHON:-$REPO_ROOT/.venv/bin/python}"
[ -x "$VENV_PYTHON" ] || VENV_PYTHON="python3"

ROOT="docs/evidence/forecasting-db-complete-evidence/$STAMP"
SC_OUT="$ROOT/01-schemacrawler-schema"
SQL_OUT="$ROOT/02-targeted-sql-profiles"
TYPE_OUT="$ROOT/03-type-normalization-profiles"
RISK_OUT="$ROOT/04-risk-tracing"
META_OUT="$ROOT/00-metadata"

mkdir -p "$SC_OUT" "$SQL_OUT" "$TYPE_OUT" "$RISK_OUT" "$META_OUT"

echo "Generating forecasting DB evidence package: $ROOT"

{
  echo "timestamp_utc=$STAMP"
  echo "repo=$(pwd)"
  echo "db=$LIVE_DB"
  echo
  echo "git_root=$(git rev-parse --show-toplevel 2>/dev/null || true)"
  echo "git_head=$(git rev-parse HEAD 2>/dev/null || true)"
  echo
  echo "git_status_short:"
  git status --short 2>/dev/null || true
} > "$META_OUT/00-run-context.txt"

sqlite3 "$LIVE_DB" 'PRAGMA quick_check;' | tee "$META_OUT/01-sqlite-quick-check.txt"

{
  stat -f "mtime=%m size=%z path=%N" "$LIVE_DB" 2>/dev/null || stat "$LIVE_DB"
  test -f "$LIVE_DB-wal" && stat -f "mtime=%m size=%z path=%N" "$LIVE_DB-wal" 2>/dev/null || true
  test -f "$LIVE_DB-shm" && stat -f "mtime=%m size=%z path=%N" "$LIVE_DB-shm" 2>/dev/null || true
  shasum -a 256 "$LIVE_DB" "$LIVE_DB-wal" "$LIVE_DB-shm" 2>/dev/null || true
} > "$META_OUT/02-db-file-fingerprints.txt"

if [ "${HB_FORECASTING_EVIDENCE_SKIP_SCHEMACRAWLER:-}" = "1" ]; then
  echo '{"ok":true,"skipped":true,"reason":"HB_FORECASTING_EVIDENCE_SKIP_SCHEMACRAWLER=1"}' > "$SC_OUT/00-schemacrawler-skipped.json"
elif command -v schemacrawler >/dev/null 2>&1; then
  schemacrawler \
    --server=sqlite \
    --database="$LIVE_DB" \
    --info-level=standard \
    --command=brief \
    --output-format=text \
    --output-file="$SC_OUT/01-brief.txt" || true

  schemacrawler \
    --server=sqlite \
    --database="$LIVE_DB" \
    --info-level=maximum \
    --command=schema \
    --output-format=text \
    --output-file="$SC_OUT/02-schema-maximum.txt" || true

  schemacrawler \
    --server=sqlite \
    --database="$LIVE_DB" \
    --info-level=maximum \
    --command=lint \
    --output-format=text \
    --output-file="$SC_OUT/04-lint.txt" || true

  schemacrawler \
    --server=sqlite \
    --database="$LIVE_DB" \
    --info-level=maximum \
    --command=schema \
    --grep-tables='.*(forecast_|procore_ep_budget|procore_ep_billing|procore_ep_change_events|procore_ep_commitment|procore_ep_prime|procore_ep_rfq|procore_ep_rfqs|procore_ep_subcontractor|procore_ep_purchase_order|second_brain_).*' \
    --output-format=text \
    --output-file="$SC_OUT/05-forecasting-family-schema.txt" || true
else
  echo '{"ok":false,"skipped":true,"reason":"schemacrawler not found on PATH"}' > "$SC_OUT/00-schemacrawler-skipped.json"
fi

"$VENV_PYTHON" - "$LIVE_DB" "$ROOT" "$REPO_ROOT" <<'PY'
import datetime as dt
import decimal
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

db_path = sys.argv[1]
root = Path(sys.argv[2])
repo_root = Path(sys.argv[3])

sys.path.insert(0, str(repo_root / "src"))
from hb_assistant.forecasting.field_classifiers import classify_amount_field, classify_date_field

sql_out = root / "02-targeted-sql-profiles"
type_out = root / "03-type-normalization-profiles"
risk_out = root / "04-risk-tracing"

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

FAMILY_PREFIXES = (
    "forecast_",
    "procore_ep_budget",
    "procore_ep_billing",
    "procore_ep_change_events",
    "procore_ep_commitment",
    "procore_ep_prime",
    "procore_ep_purchase_order",
    "procore_ep_rfqs",
    "procore_ep_rfq",
    "procore_ep_subcontractor",
    "second_brain_",
)

ADJACENT_TABLES = {
    "procore_ep_projects",
}

SENSITIVE_VALUE_COLUMNS = {
    "payload_json",
    "raw_payload",
    "raw_json",
    "body",
    "content",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "client_secret",
    "password",
}

def qid(name):
    return '"' + str(name).replace('"', '""') + '"'

def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

def rows(sql, params=()):
    return [dict(r) for r in conn.execute(sql, params).fetchall()]

def scalar(sql, params=()):
    return conn.execute(sql, params).fetchone()[0]

def all_table_names():
    return [
        r["name"]
        for r in conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
    ]

def cols(table):
    return [dict(r) for r in conn.execute(f"PRAGMA table_info({qid(table)})")]

def col_names(table):
    return [c["name"] for c in cols(table)]

def has_col(table, col):
    return col in col_names(table)

def table_exists(table):
    return table in all_tables

def safe_count(table, where="1=1"):
    try:
        return scalar(f"SELECT COUNT(*) FROM {qid(table)} WHERE {where}")
    except Exception as e:
        return {"error": str(e)}

def family_table(table):
    return table.startswith(FAMILY_PREFIXES) or table in ADJACENT_TABLES

all_tables = all_table_names()
family_tables = [t for t in all_tables if family_table(t)]

write_json(sql_out / "00-table-inventory.json", {
    "all_table_count": len(all_tables),
    "forecasting_family_table_count": len(family_tables),
    "forecasting_family_tables": family_tables,
})

write_json(sql_out / "01-column-inventory.json", {
    t: cols(t) for t in family_tables
})

fk_inventory = {}
index_inventory = {}

for t in family_tables:
    try:
        fk_inventory[t] = [dict(r) for r in conn.execute(f"PRAGMA foreign_key_list({qid(t)})")]
    except Exception as e:
        fk_inventory[t] = {"error": str(e)}

    try:
        idxs = [dict(r) for r in conn.execute(f"PRAGMA index_list({qid(t)})")]
        for idx in idxs:
            idx["columns"] = [dict(r) for r in conn.execute(f"PRAGMA index_info({qid(idx['name'])})")]
        index_inventory[t] = idxs
    except Exception as e:
        index_inventory[t] = {"error": str(e)}

write_json(sql_out / "02-foreign-key-inventory.json", fk_inventory)
write_json(sql_out / "03-index-inventory.json", index_inventory)

write_json(sql_out / "04-table-row-counts.json", [
    {"table": t, "row_count": safe_count(t)}
    for t in family_tables
])

coverage = {}

for t in family_tables:
    names = col_names(t)
    group_cols = [c for c in ["project_key", "project_id", "company_id", "endpoint_key", "is_current"] if c in names]
    profile = {"group_columns_present": group_cols, "profiles": {}}

    for c in group_cols:
        try:
            profile["profiles"][c] = rows(f"""
                SELECT CAST({qid(c)} AS TEXT) AS value, COUNT(*) AS row_count
                FROM {qid(t)}
                GROUP BY {qid(c)}
                ORDER BY row_count DESC
                LIMIT 250
            """)
        except Exception as e:
            profile["profiles"][c] = {"error": str(e)}

    coverage[t] = profile

write_json(sql_out / "05-project-endpoint-current-coverage.json", coverage)

status_like = re.compile(r"(^status$|status_|_status$|^state$|^scope$|executed|paid|private|intent_to_quote|approved|active|current|final|locked|complete|closed)", re.I)
status_distributions = {}

for t in family_tables:
    table_status = {}

    for c in col_names(t):
        if c.lower() in SENSITIVE_VALUE_COLUMNS:
            continue

        if status_like.search(c):
            try:
                table_status[c] = rows(f"""
                    SELECT CAST({qid(c)} AS TEXT) AS value, COUNT(*) AS row_count
                    FROM {qid(t)}
                    GROUP BY {qid(c)}
                    ORDER BY row_count DESC
                    LIMIT 100
                """)
            except Exception as e:
                table_status[c] = {"error": str(e)}

    if table_status:
        status_distributions[t] = table_status

write_json(sql_out / "06-status-and-flag-distributions.json", status_distributions)

def join_profile(parent, child, parent_key, child_key):
    result = {
        "parent_table": parent,
        "child_table": child,
        "parent_key": parent_key,
        "child_key": child_key,
        "evidence_basis": "row-level count validation; not proof of final business semantics",
    }

    if not table_exists(parent) or not table_exists(child):
        result["ok"] = False
        result["reason"] = "missing table"
        return result

    if not has_col(parent, parent_key) or not has_col(child, child_key):
        result["ok"] = False
        result["reason"] = "missing key column"
        return result

    p = qid(parent)
    ch = qid(child)
    pk = qid(parent_key)
    ck = qid(child_key)

    try:
        result.update({
            "ok": True,
            "parent_rows": scalar(f"SELECT COUNT(*) FROM {p}"),
            "child_rows": scalar(f"SELECT COUNT(*) FROM {ch}"),
            "parent_non_null_key_rows": scalar(f"SELECT COUNT(*) FROM {p} WHERE {pk} IS NOT NULL AND TRIM(CAST({pk} AS TEXT)) <> ''"),
            "child_non_null_key_rows": scalar(f"SELECT COUNT(*) FROM {ch} WHERE {ck} IS NOT NULL AND TRIM(CAST({ck} AS TEXT)) <> ''"),
            "matched_child_rows": scalar(f"""
                SELECT COUNT(*)
                FROM {ch} c
                WHERE c.{ck} IS NOT NULL
                  AND TRIM(CAST(c.{ck} AS TEXT)) <> ''
                  AND EXISTS (
                    SELECT 1
                    FROM {p} p
                    WHERE CAST(p.{pk} AS TEXT) = CAST(c.{ck} AS TEXT)
                  )
            """),
            "unmatched_child_rows": scalar(f"""
                SELECT COUNT(*)
                FROM {ch} c
                WHERE c.{ck} IS NOT NULL
                  AND TRIM(CAST(c.{ck} AS TEXT)) <> ''
                  AND NOT EXISTS (
                    SELECT 1
                    FROM {p} p
                    WHERE CAST(p.{pk} AS TEXT) = CAST(c.{ck} AS TEXT)
                  )
            """),
            "parent_keys_with_children": scalar(f"""
                SELECT COUNT(*)
                FROM (
                  SELECT p.{pk}
                  FROM {p} p
                  WHERE EXISTS (
                    SELECT 1
                    FROM {ch} c
                    WHERE CAST(c.{ck} AS TEXT) = CAST(p.{pk} AS TEXT)
                  )
                  GROUP BY p.{pk}
                )
            """),
            "max_children_per_parent": scalar(f"""
                SELECT COALESCE(MAX(child_count), 0)
                FROM (
                  SELECT c.{ck}, COUNT(*) AS child_count
                  FROM {ch} c
                  WHERE c.{ck} IS NOT NULL
                    AND TRIM(CAST(c.{ck} AS TEXT)) <> ''
                  GROUP BY c.{ck}
                )
            """),
        })
    except Exception as e:
        result["ok"] = False
        result["error"] = str(e)

    return result

join_specs = [
    ("procore_ep_budget_views", "procore_ep_budget_detail_rows", "record_id", "budget_view_id"),
    ("procore_ep_budget_detail_rows", "procore_ep_budget_detail_row_cells", "record_key", "record_key"),
    ("procore_ep_budget_detail_rows", "procore_ep_budget_detail_row_cells", "record_key", "primary_record_key"),
    ("procore_ep_commitment_contracts", "procore_ep_commitment_line_items", "record_id", "parent_record_id"),
    ("procore_ep_commitment_contracts", "procore_ep_commitment_change_orders", "record_id", "contract_id"),
    ("procore_ep_purchase_order_contracts", "procore_ep_purchase_order_line_items", "record_id", "holder_id"),
    ("procore_ep_purchase_order_contracts", "procore_ep_purchase_order_line_items", "record_id", "parent_record_id"),
    ("procore_ep_commitment_contracts", "procore_ep_purchase_order_line_items", "record_id", "holder_id"),
    ("procore_ep_commitment_contracts", "procore_ep_purchase_order_line_items", "record_id", "parent_record_id"),
    ("procore_ep_prime_contracts", "procore_ep_prime_contract_line_items", "record_id", "parent_record_id"),
    ("procore_ep_prime_contracts", "procore_ep_prime_change_orders", "record_id", "contract_id"),
    ("procore_ep_prime_change_orders", "procore_ep_prime_change_order_line_items", "record_id", "parent_record_id"),
    ("procore_ep_change_events", "procore_ep_change_events_change_items", "record_key", "primary_record_key"),
    ("procore_ep_change_events", "procore_ep_rfqs", "record_id", "change_event_id"),
    ("procore_ep_change_events", "procore_ep_rfqs", "record_key", "primary_record_key"),
    ("procore_ep_rfqs", "procore_ep_rfqs_change_event_change_event_line_items", "record_key", "primary_record_key"),
    ("procore_ep_billing_periods", "procore_ep_subcontractor_invoices", "record_id", "period_id"),
    ("procore_ep_commitment_contracts", "procore_ep_subcontractor_invoices", "record_id", "commitment_id"),
    ("procore_ep_subcontractor_invoices", "procore_ep_subcontractor_invoices_attachments", "record_key", "primary_record_key"),
    ("forecast_external_forecasts", "forecast_external_forecast_rows", "external_forecast_id", "external_forecast_id"),
    ("forecast_external_forecasts", "forecast_external_forecast_mappings", "external_forecast_id", "external_forecast_id"),
    ("forecast_external_forecasts", "forecast_accuracy_results", "external_forecast_id", "external_forecast_id"),
    ("forecast_external_forecasts", "forecast_comparison_results", "external_forecast_id", "external_forecast_id"),
    ("forecast_external_forecasts", "forecast_anomaly_findings", "external_forecast_id", "external_forecast_id"),
    ("forecast_external_forecasts", "forecast_review_items", "external_forecast_id", "external_forecast_id"),
]

write_json(sql_out / "07-join-cardinality-results.json", [
    join_profile(*spec) for spec in join_specs
])

amount_name = re.compile(r"(amount|cost|budget|price|value|total|balance|payment|retainage|forecast|actual|committed|contract|invoice|over|under|change_order|direct_cost|job_to_date|eac|etc|ftc|remaining)", re.I)
exclude_amount_name = re.compile(r"(id|key|code|date|time|name|description|status|type|title|number|hash|json|payload|url|path|file|email)", re.I)
amount_classifications = []

def parse_decimal(value):
    if value is None:
        return None, "null"

    s = str(value).strip()

    if s == "":
        return None, "blank"

    neg = False

    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]

    s = s.replace("$", "").replace(",", "").replace("%", "").strip()

    if s in {"-", "—", "–", "N/A", "n/a", "None", "none", "null", "NULL"}:
        return None, "blankish"

    try:
        d = decimal.Decimal(s)
        return (-d if neg else d), None
    except Exception:
        return None, "parse_error"

amount_profiles = []

for t in family_tables:
    table_cols = cols(t)

    for meta in table_cols:
        c = meta["name"]

        if c.lower() in SENSITIVE_VALUE_COLUMNS:
            continue

        classification = classify_amount_field(
            table=t,
            column=c,
            declared_type=meta.get("type"),
        )
        amount_classifications.append({
            "table": t,
            "column": c,
            "declared_type": meta.get("type"),
            **classification,
        })

        if (
            classification["approved_for_aggregation"]
            or classification["kind"] in {"true_monetary_amount", "quantity", "percentage"}
        ):
            profile = {
                "table": t,
                "column": c,
                "declared_type": meta.get("type"),
                "classification": classification,
                "non_null_count": 0,
                "blank_count": 0,
                "parse_success_count": 0,
                "parse_failure_count": 0,
                "negative_count": 0,
                "zero_count": 0,
                "min_numeric": None,
                "max_numeric": None,
                "failed_value_sha256_prefixes": [],
            }

            vals = []
            fail_hashes = []

            try:
                for r in conn.execute(f"SELECT {qid(c)} AS v FROM {qid(t)}"):
                    v = r["v"]

                    if v is not None:
                        profile["non_null_count"] += 1

                    d, err = parse_decimal(v)

                    if err in {"blank", "blankish"}:
                        profile["blank_count"] += 1
                    elif err == "parse_error":
                        profile["parse_failure_count"] += 1

                        if len(fail_hashes) < 10:
                            fail_hashes.append(hashlib.sha256(str(v).encode("utf-8", "ignore")).hexdigest()[:16])
                    elif d is not None:
                        profile["parse_success_count"] += 1
                        vals.append(d)

                        if d < 0:
                            profile["negative_count"] += 1

                        if d == 0:
                            profile["zero_count"] += 1

                if vals:
                    profile["min_numeric"] = str(min(vals))
                    profile["max_numeric"] = str(max(vals))

                profile["failed_value_sha256_prefixes"] = fail_hashes
            except Exception as e:
                profile["error"] = str(e)

            amount_profiles.append(profile)

write_json(type_out / "01-amount-parse-profile.json", amount_profiles)
write_json(type_out / "01-amount-field-classification.json", amount_classifications)

date_name = re.compile(r"(_date$|date_|_at$|_utc$|_start$|_end$|start_date|end_date|due_date|paid_date|billing_date|created|updated|submitted|executed|issued)", re.I)
date_profiles = []
date_classifications = []

for t in family_tables:
    table_cols = cols(t)

    for meta in table_cols:
        c = meta["name"]

        if c.lower() in SENSITIVE_VALUE_COLUMNS:
            continue

        date_classification = classify_date_field(
            table=t,
            column=c,
            declared_type=meta.get("type"),
        )
        date_classifications.append({
            "table": t,
            "column": c,
            "declared_type": meta.get("type"),
            **date_classification,
        })

        if date_classification["parse_as_date"]:
            profile = {
                "table": t,
                "column": c,
                "declared_type": meta.get("type"),
                "classification": date_classification,
                "non_null_count": 0,
                "blank_count": 0,
                "parse_candidate_count": 0,
                "timezone_marker_count": 0,
                "min_lexical": None,
                "max_lexical": None,
            }

            try:
                vals = []

                for r in conn.execute(f"SELECT {qid(c)} AS v FROM {qid(t)}"):
                    v = r["v"]

                    if v is None:
                        continue

                    s = str(v).strip()

                    if not s:
                        profile["blank_count"] += 1
                        continue

                    profile["non_null_count"] += 1
                    vals.append(s)

                    if re.search(r"(Z$|[+-]\d{2}:?\d{2}$)", s):
                        profile["timezone_marker_count"] += 1

                    if re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}", s):
                        profile["parse_candidate_count"] += 1

                if vals:
                    profile["min_lexical"] = min(vals)
                    profile["max_lexical"] = max(vals)
            except Exception as e:
                profile["error"] = str(e)

            date_profiles.append(profile)

write_json(type_out / "02-date-parse-profile.json", date_profiles)
write_json(type_out / "02-date-field-classification.json", date_classifications)

boolean_name = re.compile(r"^(is_|has_|can_|should_|allow_|enable_)|(_flag$|_enabled$|_active$|_current$|_private$|^paid$|^executed$|^final$|^private$)", re.I)
boolean_profiles = []

for t in family_tables:
    for c in col_names(t):
        if boolean_name.search(c):
            try:
                dist = rows(f"""
                    SELECT CAST({qid(c)} AS TEXT) AS value, COUNT(*) AS row_count
                    FROM {qid(t)}
                    GROUP BY {qid(c)}
                    ORDER BY row_count DESC
                    LIMIT 50
                """)

                boolean_profiles.append({
                    "table": t,
                    "column": c,
                    "declared_type": next((x["type"] for x in cols(t) if x["name"] == c), None),
                    "distribution": dist,
                })
            except Exception as e:
                boolean_profiles.append({
                    "table": t,
                    "column": c,
                    "error": str(e),
                })

write_json(type_out / "03-boolean-normalization-profile.json", boolean_profiles)

budget_code_cols = [
    "budget_code",
    "budget_code_id",
    "canonical_budget_code_key",
    "budget_code_key",
    "wbs_code_id",
    "wbs_flat_code",
    "wbs_code_flat_code",
    "cost_code",
    "cost_code_id",
    "cost_type",
    "cost_type_id",
    "line_item_type_id",
]

budget_profiles = {}

for t in family_tables:
    present = [c for c in budget_code_cols if c in col_names(t)]

    if not present:
        continue

    table_profile = {"columns_present": present, "column_profiles": {}}

    for c in present:
        try:
            table_profile["column_profiles"][c] = {
                "nonnull_count": scalar(f"SELECT COUNT(*) FROM {qid(t)} WHERE {qid(c)} IS NOT NULL AND TRIM(CAST({qid(c)} AS TEXT)) <> ''"),
                "distinct_count": scalar(f"SELECT COUNT(DISTINCT CAST({qid(c)} AS TEXT)) FROM {qid(t)} WHERE {qid(c)} IS NOT NULL AND TRIM(CAST({qid(c)} AS TEXT)) <> ''"),
            }
        except Exception as e:
            table_profile["column_profiles"][c] = {"error": str(e)}

    budget_profiles[t] = table_profile

write_json(sql_out / "08-budget-code-wbs-profile.json", budget_profiles)

trace_patterns = {
    "01-change-event-rfq-co-trace-coverage.json": re.compile(r"(change_event|rfq|request_for_quote|quote|commitment|prime|contract|change_order|wbs|budget_code|cost_code|vendor|amount|status)", re.I),
    "02-invoice-actualization-trace-coverage.json": re.compile(r"(invoice|billing|period|commitment|contract|line_item|change_order|payment|retainage|scheduled|completed|stored|date|amount|status|wbs|cost_code)", re.I),
}

trace_table_sets = {
    "01-change-event-rfq-co-trace-coverage.json": [
        t for t in family_tables
        if t.startswith("procore_ep_change_events")
        or t.startswith("procore_ep_rfq")
        or t.startswith("procore_ep_prime_change")
        or t.startswith("procore_ep_commitment_change")
    ],
    "02-invoice-actualization-trace-coverage.json": [
        t for t in family_tables
        if t.startswith("procore_ep_subcontractor_invoice")
        or t == "procore_ep_billing_periods"
    ],
}

for filename, pattern in trace_patterns.items():
    output = {}

    for t in trace_table_sets[filename]:
        trace_cols = [
            c for c in col_names(t)
            if pattern.search(c)
            and c.lower() not in SENSITIVE_VALUE_COLUMNS
            and not re.search(r"(json|payload|description|title|notes|comment)", c, re.I)
        ]

        table_trace = {
            "row_count": safe_count(t),
            "columns_profiled": trace_cols[:100],
            "nonnull_counts": {},
        }

        for c in trace_cols[:100]:
            try:
                table_trace["nonnull_counts"][c] = scalar(f"SELECT COUNT(*) FROM {qid(t)} WHERE {qid(c)} IS NOT NULL AND TRIM(CAST({qid(c)} AS TEXT)) <> ''")
            except Exception as e:
                table_trace["nonnull_counts"][c] = {"error": str(e)}

        output[t] = table_trace

    write_json(risk_out / filename, output)

write_json(root / "00-evidence-package-summary.json", {
    "generated_at_utc": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    "db_path": db_path,
    "forecasting_family_table_count": len(family_tables),
    "raw_payload_values_exported": False,
    "note": "Profiles use schema metadata, counts, grouped distributions, parse metrics, and hashed parse-failure fingerprints. Raw payload bodies and raw JSON values are not exported.",
    "outputs": {
        "schema": "01-schemacrawler-schema/",
        "table_inventory": "02-targeted-sql-profiles/00-table-inventory.json",
        "column_inventory": "02-targeted-sql-profiles/01-column-inventory.json",
        "foreign_key_inventory": "02-targeted-sql-profiles/02-foreign-key-inventory.json",
        "index_inventory": "02-targeted-sql-profiles/03-index-inventory.json",
        "row_counts": "02-targeted-sql-profiles/04-table-row-counts.json",
        "coverage": "02-targeted-sql-profiles/05-project-endpoint-current-coverage.json",
        "status_distributions": "02-targeted-sql-profiles/06-status-and-flag-distributions.json",
        "join_cardinality": "02-targeted-sql-profiles/07-join-cardinality-results.json",
        "budget_code_wbs_profile": "02-targeted-sql-profiles/08-budget-code-wbs-profile.json",
        "amount_parse_profile": "03-type-normalization-profiles/01-amount-parse-profile.json",
        "amount_field_classification": "03-type-normalization-profiles/01-amount-field-classification.json",
        "date_parse_profile": "03-type-normalization-profiles/02-date-parse-profile.json",
        "date_field_classification": "03-type-normalization-profiles/02-date-field-classification.json",
        "boolean_normalization_profile": "03-type-normalization-profiles/03-boolean-normalization-profile.json",
        "change_event_trace": "04-risk-tracing/01-change-event-rfq-co-trace-coverage.json",
        "invoice_trace": "04-risk-tracing/02-invoice-actualization-trace-coverage.json",
    },
})
PY

find "$ROOT" -name '*.json' -print0 | xargs -0 -n1 "$VENV_PYTHON" -m json.tool >/dev/null

ZERO_TMP="$ROOT/99-zero-byte-files.tmp"
find "$ROOT" -type f -size 0 ! -name '99-zero-byte-files.txt' ! -name '99-zero-byte-files.tmp' -print | tee "$ZERO_TMP" >/dev/null
mv "$ZERO_TMP" "$ROOT/99-zero-byte-files.txt"

if [ "${HB_FORECASTING_EVIDENCE_SKIP_NO_RAW:-}" = "1" ]; then
  echo '{"ok":true,"skipped":true,"reason":"HB_FORECASTING_EVIDENCE_SKIP_NO_RAW=1","live_calls_disabled":true,"writeback":"none","unsafe_finding_count":0}' > "$ROOT/98-no-raw-leak-scan.json"
elif [ -x ".venv/bin/hb-assistant" ]; then
  .venv/bin/hb-assistant procore analytics no-raw-leak-scan \
    --path "$ROOT" \
    --json | tee "$ROOT/98-no-raw-leak-scan.json" >/dev/null
elif command -v hb-assistant >/dev/null 2>&1; then
  hb-assistant procore analytics no-raw-leak-scan \
    --path "$ROOT" \
    --json | tee "$ROOT/98-no-raw-leak-scan.json" >/dev/null
else
  echo '{"ok":false,"skipped":true,"reason":"hb-assistant not found"}' > "$ROOT/98-no-raw-leak-scan.json"
fi

"$VENV_PYTHON" -m json.tool "$ROOT/98-no-raw-leak-scan.json" >/dev/null

TGZ="docs/evidence/forecasting-db-complete-evidence-$STAMP.tgz"
CHECKSUM_SIDEcar="${TGZ}.sha256"

{
  echo "generated_at_utc=$STAMP"
  echo "OUT=$ROOT"
  echo "TGZ=$TGZ"
  echo "packaging_step=pre_tar"
} > "$ROOT/96-package-complete.txt"

find "$ROOT" -type f | sort > "$ROOT/97-file-manifest.txt"

COPYFILE_DISABLE=1 tar --exclude='._*' -czf "$TGZ" -C "docs/evidence/forecasting-db-complete-evidence" "$STAMP"

TAR_SHA="$(shasum -a 256 "$TGZ" 2>/dev/null | awk '{print $1}')"
{
  echo "generated_at_utc=$STAMP"
  echo "OUT=$ROOT"
  echo "TGZ=$TGZ"
  echo "tarball_sha256=$TAR_SHA"
  echo "packaging_step=post_tar"
} | tee "$ROOT/96-package-complete.txt"

echo "$TAR_SHA  $TGZ" > "$CHECKSUM_SIDEcar"

echo "$TGZ"
