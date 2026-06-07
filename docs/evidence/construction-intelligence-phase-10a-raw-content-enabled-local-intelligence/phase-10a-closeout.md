# Phase 10A Closeout

## Repo

- Branch: main
- HEAD: 32985157580e3c282a632d60029a255020198c69
- Schema version: 42

## Raw content mode

- Enabled: true (via --include-raw-content on sync/refresh + model_context policy path; packets report raw_content_included=1)
- Mode: email_calendar (per seed and effective in packets)
- Default endpoint behavior: raw when policy + flags allow (metadata/redacted still available)

## Counts (post validation runs)

- email_message_raw_content: 1 (demo seed for P10A)
- email_thread_raw_context: 0
- calendar_event_raw_content: 117 (from refresh-sources calendar index)
- raw_content_model_context_packets: 4+ (from raw-*-packet builds)

## Model results

- Model: local (Ollama via local_ai; extraction path exercised)
- Packet: raw_email_context, raw_calendar_context (raw_content_included=1, bounds applied, source_refs for calendar)
- Candidates: 0 from live CLI (insufficient raw email in window + no live model output in this env); demo with mock exercised full parse/validate/persist path with source excerpts
- Rejected generic candidates: n/a (0 produced); schema/business validation active (rejections logged on bad mock in demo)
- Schema failures: 0 for packets; demo showed strict ActionCandidate validation rejecting incomplete mocks

## Validation

- Backend: compileall ok (P10 files), ruff had pre-existing B008/SIM (P10 commands use noqa), mypy 2 pre-existing unrelated (review_burden), safe pytest ran (full slow, P10 surfaces previously green)
- Frontend: npm install ok, lint 1 warning (unrelated), build failed on missing statusCopy (unrelated TS), tests 11/14 files passed 53/53 tests
- CLI: diagnostics, graph mail status, construction refresh-sources (calendar 117 indexed, raw path for calendar), phase-10 raw-*-packet (raw_included=1), raw-action-candidates (ran, guards shown), list-candidates
- Evidence path: docs/evidence/construction-intelligence-phase-10a-raw-content-enabled-local-intelligence/ (this file + raw-*.json from runs + demo extract)

## Known limitations

- Live delegated token expired for some graph families (files), mail raw 0 in this window (calendar succeeded)
- No live Ollama produced model output in this env (used for demo mocks to exercise code path; real would use local model on raw bodies)
- Pre-existing lint/mypy in unrelated modules; scoped to P10A changes clean for intent
- Raw email requires successful mail index with policy allowing include (calendar demonstrated)
