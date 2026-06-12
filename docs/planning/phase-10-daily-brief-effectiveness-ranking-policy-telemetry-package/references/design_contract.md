# Design Contract

## Authority Hierarchy

1. Human operator lifecycle decisions are authoritative.
2. Existing lifecycle/read-model state is authoritative for disposition.
3. Source refs are authoritative for traceability; telemetry may count them but must not alter them.
4. Deterministic ranking rules remain authoritative over model advice.
5. Local model advice is advisory only and can be evaluated but not promoted to authority.
6. Telemetry can recommend next tuning actions but cannot apply them.

## Input Contract

Telemetry may read only structured/redacted/hashed metadata from:

- ranked candidate rows from the prerequisite ranking/assembly slice;
- assembled section metadata;
- `daily_brief_action_candidates` safe fields;
- `candidate_source_refs` hashes/counts;
- V50 lifecycle overlay and computed review queue/read model;
- `local_model_run_receipts` and model ranking receipt metadata;
- duplicate/similarity edge metadata from the prerequisite slice;
- output/render receipts that store hashes/path-redacted metadata only.

Telemetry must not read raw tables unless it is proving they are not being read. Do not use `include_raw` render paths.

## Output Contract

Outputs may contain:

- counts;
- rates;
- scores;
- policy/model/profile ids;
- reason codes;
- hashes;
- scanner category codes;
- aggregate recommendations.

Outputs must include:

- data window;
- sample size;
- confidence note;
- insufficient sample flag when sample is small;
- degradation status when data is absent or incomplete.

## Read-Only / No-Writeback Contract

- Packet building and metric computation are pure/read-only.
- Apply mode may persist telemetry rows only.
- Apply mode cannot mutate candidate/lifecycle/source-ref/ranking/assembly source tables.
- External writeback is forbidden.

## Report Contract

The report/dashboard is raw-free and must scan clean. It should include:

- brief usefulness trend;
- accepted/rejected/snoozed/ignored summary;
- rank-outcome alignment;
- source-ref coverage;
- Procore noise summary;
- model reliability/degradation;
- duplicate/similarity proxy;
- feedback calibration lift;
- safe next tuning recommendations.
