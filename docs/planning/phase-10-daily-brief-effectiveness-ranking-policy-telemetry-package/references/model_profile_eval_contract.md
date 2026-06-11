# Model Profile Evaluation Contract

## Purpose

Measure reliability and advisory utility of local model profiles used by ranking/assembly without retaining raw prompt/output.

## Inputs

- model profile id/name;
- local model run receipt ids;
- task type;
- status;
- schema_valid;
- fallback_used;
- latency;
- output hash;
- safety/degradation reason codes.

## Metrics

- attempt count;
- success count;
- schema invalid count;
- safety withheld count;
- timeout count;
- fallback count;
- average/p95 latency;
- advisory adoption proxy;
- model degradation rate.

## Prohibitions

- no raw prompt;
- no raw response;
- no hidden context;
- no external model telemetry.
