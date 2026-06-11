# 19 — CLI Help Snapshots (operator surfaces for the first slice)

Captured via `hb-assistant ... --help`. These existing commands already support `--db`
(copy validation), dry-run default, and `--apply`/`--json`; no new commands were required.

## `hb-assistant email-calendar raw projection-reprocess --help`
```
                                                                                                    
 Usage: hb-assistant email-calendar raw projection-reprocess                                        
            [OPTIONS]                                                                               
                                                                                                    
 Project raw rows into the structured tables.                                                       
                                                                                                    
 Dry-run by default (zero writes). A REAL apply requires all three: --apply (opt in), --no-dry-run  
 (override the safe default), and an explicit --db (so it never targets the production DB           
 implicitly). See the operator runbook for the bounded rollout sequence.                            
                                                                                                    
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────╮
│ --db                         TEXT  Explicit SQLite DB path (required for --apply).               │
│ --family                     TEXT  email_message | email_thread | calendar_event                 │
│ --dry-run    --no-dry-run          Preview only (default). Pass --no-dry-run together with       │
│                                    --apply to persist.                                           │
│                                    [default: dry-run]                                            │
│ --apply                            Persist projection rows. A real apply requires --apply AND    │
│                                    --no-dry-run AND --db.                                        │
│ --json       --no-json             [default: json]                                               │
│ --help                             Show this message and exit.                                   │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯

```

## `hb-assistant email-calendar raw projection-coverage --help`
```
                                                                                                    
 Usage: hb-assistant email-calendar raw projection-coverage                                         
            [OPTIONS]                                                                               
                                                                                                    
 Completeness coverage (zero unmapped primary/nested business fields). Exit 3 on unmapped.          
                                                                                                    
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────╮
│ --db                   TEXT  Explicit SQLite DB path (use a /tmp copy).                          │
│ --json    --no-json          [default: json]                                                     │
│ --help                       Show this message and exit.                                         │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯

```

## `hb-assistant email-calendar raw status --help`
```
                                                                                                    
 Usage: hb-assistant email-calendar raw status [OPTIONS]                                            
                                                                                                    
 Raw + structured row counts and source-quality distribution (counts only).                         
                                                                                                    
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────╮
│ --db                   TEXT  Explicit SQLite DB path.                                            │
│ --json    --no-json          [default: json]                                                     │
│ --help                       Show this message and exit.                                         │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯

```

## `hb-assistant second-brain calendar-prep build --help`
```
                                                                                                    
 Usage: hb-assistant second-brain calendar-prep build [OPTIONS]                                     
                                                                                                    
 Build deterministic, source-linked calendar meeting-prep candidates (dry-run-first).               
                                                                                                    
 Discovers upcoming, non-cancelled, non-private events within the lookahead window and builds one   
 bounded, redacted prep candidate per event (join URLs / dial-in / passcodes stripped; attendees    
 reduced to counts + domains; never raw subjects/bodies). Defaults to dry-run (zero writes);        
 --apply is explicit and REQUIRES --max-persist, capping idempotent inserts into                    
 daily_brief_action_candidates (section calendar). --synthesize adds an optional, in-memory         
 advisory narrative fed ONLY redacted aggregates. No calendar/external writeback, no cloud LLM.     
                                                                                                    
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────╮
│ --project                       TEXT     Single project key (default: all events in window).     │
│ --as-of                         TEXT     ISO-8601 UTC 'now' for the deterministic lookahead      │
│                                          window / brief-date (default: current UTC).             │
│ --lookahead-days                INTEGER  Forward window in days from --as-of (events starting    │
│                                          within).                                                │
│                                          [default: 14]                                           │
│ --limit                         INTEGER  Max upcoming events to consider (soonest-first; bounds  │
│                                          output AND would-persist). --max-persist is the         │
│                                          separate hard cap on actual writes.                     │
│                                          [default: 50]                                           │
│ --dry-run            --apply             Dry-run (default; zero writes). --apply persists,       │
│                                          capped by --max-persist.                                │
│                                          [default: dry-run]                                      │
│ --max-persist                   INTEGER  REQUIRED with --apply: cap on ACTUAL persisted          │
│                                          candidates.                                             │
│ --synthesize                             Optional bounded local-model advisory narrative (off by │
│                                          default; in-memory only).                               │
│ --profile                       TEXT     Local model profile when --synthesize                   │
│                                          (default_extract).                                      │
│                                          [default: default_extract]                              │
│ --model                         TEXT     Override the synthesis model (default from profile:     │
│                                          mistral-nemo:12b).                                      │
│ --provider                      TEXT     Local model provider (ollama).                          │
│                                          [default: ollama]                                       │
│ --timeout-seconds               FLOAT    Override the synthesis model timeout.                   │
│ --summary                                Include the full per-event prep list (redacted          │
│                                          excerpts) in the response.                              │
│ --db                            TEXT     Explicit SQLite path (tests/isolation).                 │
│ --json                                   Emit JSON (default).                                    │
│                                          [default: True]                                         │
│ --help                                   Show this message and exit.                             │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯

```

## `hb-assistant second-brain procore-digest build --help`
```
                                                                                                    
 Usage: hb-assistant second-brain procore-digest build [OPTIONS]                                    
                                                                                                    
 Build a deterministic, source-linked Procore action-signal digest (dry-run-first).                 
                                                                                                    
 Composes the existing redacted Procore rollup read models into per-project, per-signal-type groups 
 (counts, overdue, dimensions, bounded source refs). Defaults to dry-run (zero writes); --apply is  
 explicit and REQUIRES --max-persist, capping inserts into daily_brief_action_candidates            
 (idempotent rollups). --synthesize adds an optional, in-memory advisory narrative fed ONLY         
 redacted aggregates. No Procore/external writeback, no cloud LLM.                                  
                                                                                                    
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────╮
│ --project                       TEXT     Single Procore project key (default: all projects       │
│                                          present).                                               │
│ --as-of                         TEXT     ISO-8601 UTC 'now' for deterministic overdue/brief-date │
│                                          (default: current UTC).                                 │
│ --limit                         INTEGER  Max signal-type groups per project (highest-count       │
│                                          first; bounds output AND would-persist). --max-persist  │
│                                          is the separate hard cap on actual writes.              │
│                                          [default: 50]                                           │
│ --dry-run            --apply             Dry-run (default; zero writes). --apply persists,       │
│                                          capped by --max-persist.                                │
│                                          [default: dry-run]                                      │
│ --max-persist                   INTEGER  REQUIRED with --apply: cap on ACTUAL persisted          │
│                                          candidates.                                             │
│ --synthesize                             Optional bounded local-model advisory narrative (off by │
│                                          default; in-memory only).                               │
│ --profile                       TEXT     Local model profile when --synthesize                   │
│                                          (default_extract).                                      │
│                                          [default: default_extract]                              │
│ --model                         TEXT     Override the synthesis model (default from profile:     │
│                                          mistral-nemo:12b).                                      │
│ --provider                      TEXT     Local model provider (ollama).                          │
│                                          [default: ollama]                                       │
│ --timeout-seconds               FLOAT    Override the synthesis model timeout.                   │
│ --summary                                Include the full per-project groups list in the         │
│                                          response.                                               │
│ --db                            TEXT     Explicit SQLite path (tests/isolation).                 │
│ --json                                   Emit JSON (default).                                    │
│                                          [default: True]                                         │
│ --help                                   Show this message and exit.                             │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯

```

## `hb-assistant second-brain daily-run run --help`
```
                                                                                                    
 Usage: hb-assistant second-brain daily-run run [OPTIONS]                                           
                                                                                                    
 Run the weekday-aware daily local-agent workflow once (dry-run-first; advisory).                   
                                                                                                    
 Resolves the weekday date policy (Monday carryover / standard / Friday next-week prep; weekend     
 skip or Saturday catch-up of a missed Friday), runs the pipeline with that window, renders the raw 
 brief to a governed Obsidian note + a self-contained browser HTML file at stable NON-repo paths,   
 writes a redacted status file, and preserves the last successful brief on failure. The browser is  
 never auto-opened.                                                                                 
                                                                                                    
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────╮
│ --as-of                                                      TEXT     ISO-8601 local run time    │
│                                                                       (default: now). Its        │
│                                                                       weekday drives the policy. │
│ --date                                                       TEXT     Force the brief date       │
│                                                                       YYYY-MM-DD (run at 05:00   │
│                                                                       local that day).           │
│ --timezone                                                   TEXT     Local timezone for the     │
│                                                                       weekday date policy.       │
│                                                                       [default:                  │
│                                                                       America/New_York]          │
│ --dry-run                      --apply                                Dry-run (default; zero     │
│                                                                       writes). --apply persists  │
│                                                                       (capped).                  │
│                                                                       [default: dry-run]         │
│ --max-persist-per-stage                                      INTEGER  Conservative per-stage     │
│                                                                       persist cap.               │
│                                                                       [default: 10]              │
│ --max-total-persist                                          INTEGER  Conservative global        │
│                                                                       persist ceiling.           │
│                                                                       [default: 30]              │
│ --limit                                                      INTEGER  Per-stage item cap.        │
│                                                                       [default: 50]              │
│ --lookahead-days                                             INTEGER  Calendar fallback window   │
│                                                                       (policy window takes       │
│                                                                       precedence).               │
│                                                                       [default: 14]              │
│ --raw                          --no-raw                               Raw local content in the   │
│                                                                       Obsidian + browser brief   │
│                                                                       (default on).              │
│                                                                       [default: raw]             │
│ --weekdays-only                --all-days                             Skip weekend runs          │
│                                                                       (default; Mon–Fri only).   │
│                                                                       [default: weekdays-only]   │
│ --write-obsidian                                                      Write the governed         │
│                                                                       Obsidian note (requires    │
│                                                                       confirmation).             │
│ --confirm-vault-write                                                 REQUIRED with              │
│                                                                       --write-obsidian (governed │
│                                                                       vault write).              │
│ --vault-brief-dir                                            TEXT     Override the governed      │
│                                                                       vault brief dir            │
│                                                                       (test/isolation).          │
│ --generate-browser             --no-generate-browser                  Generate the browser HTML  │
│                                                                       brief.                     │
│                                                                       [default:                  │
│                                                                       generate-browser]          │
│ --browser-output-dir                                         TEXT     Browser HTML output dir    │
│                                                                       (default:                  │
│                                                                       app-support/html).         │
│ --status-dir                                                 TEXT     Status-file dir (default:  │
│                                                                       app-support/daily-run-sta… │
│ --synthesize                   --no-synthesize                        Local-model executive      │
│                                                                       synthesis of the brief     │
│                                                                       (apply only; fail-closed → │
│                                                                       degraded brief on model    │
│                                                                       failure/low-quality, never │
│                                                                       a silent candidate dump).  │
│                                                                       [default: synthesize]      │
│ --synthesis-profile                                          TEXT     Local model profile id for │
│                                                                       synthesis (benchmark:      │
│                                                                       default_extract vs         │
│                                                                       review_filter).            │
│                                                                       [default: brief_synthesis] │
│ --model-enriched-intellige…    --no-model-enriched-intel…             DEFAULT-ON: render the     │
│                                                                       single converged 'Model    │
│                                                                       Enriched Intelligence'     │
│                                                                       section (source-linked     │
│                                                                       advisory bullets + pending │
│                                                                       V45 email follow-up rows)  │
│                                                                       on the browser, Obsidian,  │
│                                                                       status, and CLI surfaces.  │
│                                                                       Advisory/source-linked,    │
│                                                                       never accepted fact; fails │
│                                                                       closed to the              │
│                                                                       deterministic brief. Use   │
│                                                                       --no-model-enriched-intel… │
│                                                                       to disable.                │
│                                                                       [default:                  │
│                                                                       model-enriched-intelligen… │
│ --with-intelligence            --no-intelligence                      Back-compat alias:         │
│                                                                       additionally attach the    │
│                                                                       standalone advisory        │
│                                                                       intelligence object to the │
│                                                                       --json payload. The        │
│                                                                       brief's 'Model Enriched    │
│                                                                       Intelligence' section is   │
│                                                                       now default-on (see        │
│                                                                       --model-enriched-intellig… │
│                                                                       this flag only adds the    │
│                                                                       JSON twin. Off by default. │
│                                                                       [default: no-intelligence] │
│ --email-raw-enrichment         --no-email-raw-enrichment              DEFAULT-ON (apply only):   │
│                                                                       run the bounded, capped,   │
│                                                                       idempotent, source-linked  │
│                                                                       V45 email raw enrichment   │
│                                                                       stage so newly review-safe │
│                                                                       rows feed the Model        │
│                                                                       Enriched Intelligence      │
│                                                                       section the same run.      │
│                                                                       Dry-run reports            │
│                                                                       would-persist and writes   │
│                                                                       nothing; apply is capped   │
│                                                                       by                         │
│                                                                       --email-raw-enrichment-ma… │
│                                                                       (else                      │
│                                                                       --max-persist-per-stage).  │
│                                                                       Local-only; never raw.     │
│                                                                       [default:                  │
│                                                                       email-raw-enrichment]      │
│ --email-raw-enrichment-max…                                  INTEGER  Cap on ACTUAL V45          │
│                                                                       enrichment writes in apply │
│                                                                       mode (default:             │
│                                                                       --max-persist-per-stage).  │
│ --with-email-raw-enrichment    --no-with-email-raw-enric…             Back-compat alias: also    │
│                                                                       attach the structured      │
│                                                                       PENDING V45 email          │
│                                                                       follow-up section as a     │
│                                                                       machine-readable twin to   │
│                                                                       the --json payload. The    │
│                                                                       rendered brief already     │
│                                                                       surfaces pending           │
│                                                                       review-safe enrichments    │
│                                                                       under 'Model Enriched      │
│                                                                       Intelligence'. Read-only;  │
│                                                                       off by default.            │
│                                                                       [default:                  │
│                                                                       no-with-email-raw-enrichm… │
│ --open-browser                 --no-open-browser                      Reserved — auto-open is    │
│                                                                       NOT enabled yet; the       │
│                                                                       browser is never opened.   │
│                                                                       [default: no-open-browser] │
│ --allow-partial                                                       Exit 0 even on a           │
│                                                                       partial/failed run         │
│                                                                       (payload still reports     │
│                                                                       it).                       │
│ --include-relationship-can…    --no-relationship-candida…             OPT-IN: run the            │
│                                                                       cross-source               │
│                                                                       relationship-candidate     │
│                                                                       stage before render (off   │
│                                                                       by default; the scheduled  │
│                                                                       daily run is unchanged).   │
│                                                                       When applied, it populates │
│                                                                       relationship rows the      │
│                                                                       brief then surfaces as a   │
│                                                                       'Related Context' section. │
│                                                                       [default:                  │
│                                                                       no-relationship-candidate… │
│ --relationship-scan-threads                                  INTEGER  Relationship stage: max    │
│                                                                       email threads to scan      │
│                                                                       (default: stage default    │
│                                                                       50). Widen this (e.g. 200) │
│                                                                       so the scheduled run finds │
│                                                                       relationships on a fuller  │
│                                                                       mailbox.                   │
│ --relationship-scan-events                                   INTEGER  Relationship stage: max    │
│                                                                       calendar events to scan    │
│                                                                       (default: stage default    │
│                                                                       50).                       │
│ --db                                                         TEXT     Explicit SQLite path       │
│                                                                       (tests/isolation).         │
│ --json                                                                Emit JSON (default).       │
│                                                                       [default: True]            │
│ --help                                                                Show this message and      │
│                                                                       exit.                      │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯

```
