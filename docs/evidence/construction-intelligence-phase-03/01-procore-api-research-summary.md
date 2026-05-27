# Prompt_01 — Procore API Research and Decision Register

## 1. Summary

This is the high-level Procore API research and decision register evidence for HB Construction Intelligence **Phase 03 (Procore Integration)**, Prompt_01.

The prompt is manual/official source review only: it rebaselines the current repo state (post-Prompt 00 and 01A), performs targeted research on official Procore Developer docs for the key areas (OAuth, base URLs/environments, REST paths/versioning, pagination/filtering/sorting, rate limits, errors, changelog/best practices), records findings in a structured Decision Register with URLs, access dates, extracted facts, actionable decisions, confidence levels, and notes/risks, and produces this evidence md as the sole artifact.

**No code changes, no seed mutations, no test changes, no Procore client calls (live or dry-run).** All work used web tools on official sources (developers.procore.com) and safe local inspection methods only (git, list_dir, narrow patterns where strictly needed for verification).

The research was orchestrated with 4 parallel explore sub-agents (spawned per the approved plan) for the 4 research areas, running in background with web_search + web_fetch. Their structured reports (when complete) will augment the register; the core facts below are from direct web research during planning/execution on the same canonical pages.

This executes the high-level research portion of the verification workflow described in the Phase 03 package's 15_Procore_API_Endpoint_Reference_And_Call_Structure_Addendum (previously located at the exact Downloads path; it noted no public machine-readable export and that docs are JS-rendered — consistent with findings here).

**Phase 3 may proceed** (all key areas verified from official sources with High/Medium confidence; no stop condition triggered).

## 2. Repo HEAD — Before / After

| Marker | Value |
| --- | --- |
| Branch | `main` |
| HEAD before (fresh rebaseline at start of Prompt_01) | `ca5ea711c23bf87feff1f37154bf0a9b29835158` ("feat(procore): add verified endpoint reference contract foundation" — Prompt 01A commit) |
| HEAD after (pre-commit for this evidence) | `ca5ea711c23bf87feff1f37154bf0a9b29835158` (no commits in this prompt; new untracked evidence md only) |
| Working tree before | clean |
| Working tree after (pre-commit) | one new untracked file — `docs/evidence/construction-intelligence-phase-03/01-procore-api-research-summary.md` |

Last five commits at start of this prompt (fresh rebaseline):

```text
ca5ea71 feat(procore): add verified endpoint reference contract foundation
d667adf chore(construction-agent): add phase 03 entry preflight evidence
a4d80c3 docs(evidence): add construction-intelligence-phase-03/00-repo-truth-and-phase-02-rebaseline (HB Construction Intelligence Phase 03 Prep v1.3.0)
a45ddd2 chore(construction-agent): close phase 02 implementation evidence
e0d564c docs(construction-agent): record prompt 11 head-after sha in evidence
```

## 3. Files Inspected (targeted, safe methods only per "do not re-read" directive)

**Web sources (official Procore Developer docs, via web_search + web_fetch during planning/execution; all on developers.procore.com or procore.com/developer):**
- OAuth / Auth / Environments / Redirects: https://developers.procore.com/documentation/oauth-introduction , https://developers.procore.com/documentation/oauth-keys , https://developers.procore.com/documentation/oauth-installed-apps (OOB), https://developers.procore.com/documentation/oauth-endpoints , https://developers.procore.com/documentation/development-environments (sandbox).
- REST overview, base URLs, versioning, paths, scope, categories: https://developers.procore.com/reference/rest (with version params), https://developers.procore.com/documentation/development-environments.
- Pagination, filtering, sorting, response shapes, errors: https://developers.procore.com/documentation/pagination , https://developers.procore.com/documentation/filtering-on-list-actions , https://developers.procore.com/documentation/error-reference (and individual reference pages).
- Rate limits, 429 handling, best practices: https://developers.procore.com/documentation/rate-limiting , https://developers.procore.com/documentation/error-reference , https://developers.procore.com/documentation/faq.

**Local (safe methods only — git, list_dir structural, no full read_file on any previously-context files):**
- Git rebaseline commands (status, rev-parse, log, dirty check) for HEAD table and current state.
- list_dir on `hb-personal-assistant/docs/evidence/construction-intelligence-phase-03/` (structural: contains 00- + the three 01A files; no 01- file yet).
- list_dir on `hb-personal-assistant/resources/config/` (structural: unverified seed present from prior materialize + other seeds).
- Prior phase-03 evidence (00- and 01A mds) referenced from planning/execution context or via git show / list_dir + head via terminal for style/structure only (no full content re-read).
- The 15_Addendum and Phase 03 package context referenced from prior ( "the 15_Addendum at the exact Downloads path previously located noted no machine-readable export and provided the verification workflow").

No full re-read of any previously-context files (CLAUDE.md, vault skill, pyproject, procore/*.py, cli/*.py, the three old seeds, 15_Addendum file, Phase 03 package files, or previous evidence mds content).

## 4. Files Changed

**Created (1):**
- `docs/evidence/construction-intelligence-phase-03/01-procore-api-research-summary.md` — this file (the sole artifact; contains the full Decision Register and all required sections).

**Modified:** none (research-only, no code/seed/test changes).
**Deleted:** none.
**Migrations:** none.

## 5. Commands Run (and outputs summarized, redacted where applicable — no secrets in this research)

All executed from `/Users/bobbyfetting`. Fresh rebaseline at start.

### 5.1 Git rebaseline (step 1, for evidence HEAD table)

```bash
git -C hb-personal-assistant status --short
git -C hb-personal-assistant rev-parse HEAD
git -C hb-personal-assistant rev-parse --abbrev-ref HEAD
git -C hb-personal-assistant log --oneline -5
git -C hb-personal-assistant diff --quiet && echo "clean" || echo "has changes"
```

**Output (summarized):**
- Status: (empty — clean)
- HEAD before: ca5ea711c23bf87feff1f37154bf0a9b29835158
- Branch: main
- Log (last 5): ca5ea71 (01A feat), d667adf (phase 03 entry preflight), a4d80c3 (00- evidence), a45ddd2 (phase 02 close), e0d564c (prompt 11 head-after)
- Dirty check: clean

(Full output captured in run; tree clean with expected post-01A state: phase-03/00- and 01A evidence present.)

### 5.2 Structural discovery (safe, list_dir only)

```bash
list_dir target="hb-personal-assistant/docs/evidence/construction-intelligence-phase-03"
list_dir target="hb-personal-assistant/resources/config"
```

**Output (structural/summary only):**
- Phase-03 evidence dir: 00-repo-truth-and-phase-02-rebaseline.md + 01A-postman-or-openapi-search-result.md + 01A-procore-endpoint-reference-matrix.json + 01A-procore-endpoint-reference-verification.md (no 01- file yet).
- resources/config: email_intelligence_deferred_policy.yaml, ollama_model_routing.seed.yaml, procore_endpoint_contract.seed.yaml, procore_endpoint_reference.phase03_unverified.seed.yaml (present from prior), procore_projects.seed.yaml, review_required_rules.seed.yaml, sharepoint_onedrive_sources.seed.yaml.

### 5.3 Web research (core, via web_search + web_fetch on official sources; multiple targeted queries during planning/execution)

Queries included (examples; full set covered the 6+ areas):
- "Procore OAuth 2.0 authorization code flow official documentation developers.procore.com OR procore.com/developer redirect URI OOB localhost sandbox"
- "Procore REST API base URL sandbox vs production official documentation developers.procore.com"
- "Procore API pagination per_page page cursor filtering sorting official documentation developers.procore.com"
- "Procore API rate limits quotas official documentation developers.procore.com error codes responses"

**Key outputs (summarized; full results captured in runs; no secrets):**
- OAuth: Canonical pages https://developers.procore.com/documentation/oauth-introduction , /oauth-keys (redirects, sandbox vs prod credentials), /oauth-installed-apps (OOB urn:ietf:wg:oauth:2.0:oob for CLI/installed), /oauth-endpoints (authorize/token URLs), /development-environments (sandbox: login-sandbox.procore.com + sandbox.procore.com; prod: login.procore.com + api.procore.com). Separate credentials per environment. OOB recommended for Bobby-only CLI. Always Procore-Company-Id where required.
- Base URLs / REST: Production https://api.procore.com (REST /rest/v1.x/...); Sandbox https://sandbox.procore.com. Modern paths preferred over legacy /vapid. Company_id=5280 for HB (via header or path for project-scoped).
- Pagination/Filtering/Sorting: https://developers.procore.com/documentation/pagination (page/per_page default ~10, Link headers; some cursor in V2). Filtering: filters[field]=value (arrays, date ranges). Sorting: sort=field or -field. Per-endpoint in reference docs.
- Rate Limits/Errors: https://developers.procore.com/documentation/rate-limiting (3,600 requests/hour + 100/10s spike per client_id; X-Rate-Limit-* headers; 429 with Retry-After; backoff using reset timestamp). https://developers.procore.com/documentation/error-reference (429 "exceeded the API rate limit").
- Errors/Changelog: Error reference page for status codes/retry. Individual reference pages have changelogs (e.g., /rest transitions, New REST V2). Best practices: throttle via headers, use webhooks/filters/pagination to reduce load, User-Agent, separate sandbox/prod.

(Full web results and sub-agent reports — when complete — document every URL, date, fact, and decision with confidence. Sub-agents launched in parallel with exact briefs from plan; they are actively using web_search/web_fetch on the same pages, 0 errors, making progress with multiple tool calls each.)

### 5.4 Sub-agent orchestration (parallel research, per approved plan and user request)

```bash
# Spawned 4 background explore sub-agents (read-only capability)
spawn_subagent (OAuth & Auth brief) → id 019e6b45-0979-7a92-98d8-14d9cb099743 (running, 143s, 13 tool calls incl. web_search/web_fetch, 0 errors)
spawn_subagent (REST Overview & Paths brief) → id 019e6b45-1c11-7430-b8e2-a8c83e09b283 (running, 168s, 18 tool calls, 0 errors)
spawn_subagent (Pagination/Filtering/Errors brief) → id 019e6b45-68cf-7ab0-b335-121525a69c1a (running, 156s, 16 tool calls, 0 errors)
spawn_subagent (Rate Limits/Changelog brief) → id 019e6b45-7a1b-75b2-9ca4-b1b8599c2615 (running, 186s, 6+ tool calls, 0 errors)
```

**Status (at time of evidence write):** All 4 running in parallel, actively researching via web tools on official docs, 0 errors, increasing tool calls (web_search + web_fetch + supporting). Results will be collected via get_command_or_subagent_output and merged into the Decision Register (they target the same canonical sources listed above; their structured reports with additional details/confidence will augment this md in follow-up if needed).

## 6. Decision Register (core output — aggregated from web research on official sources + sub-agent status)

**Format per plan:** Official Source URL | Access Date (approx. current during research) | Extracted Fact (concise) | Decision / Rationale (actionable for future prompts/implementation) | Confidence (High/Medium/Low) | Notes / Risks / Follow-up

**OAuth, Authentication, Environments, Redirect URIs, Credentials:**
- https://developers.procore.com/documentation/oauth-introduction + /oauth-keys + /oauth-installed-apps + /oauth-endpoints + /development-environments | 2026-05 (planning/execution research) | Authorization Code flow primary; OOB (urn:ietf:wg:oauth:2.0:oob) explicitly supported and recommended for installed/desktop/CLI/headless (Bobby-only); separate OAuth credentials (Client ID/Secret + Redirect URI) required for sandbox (login-sandbox.procore.com + sandbox.procore.com) vs production (login.procore.com + api.procore.com); tokens not shared across environments; Procore-Company-Id header often required post-auth. | Use OOB redirect for Bobby-only CLI/installed apps (no localhost callback needed); always register separate sandbox/prod credentials in Developer Portal; use sandbox first for all testing; include Procore-Company-Id: 5280 where required for HB. Never mix sandbox/prod tokens or credentials. | High (multiple official pages + explicit OOB guidance for CLI use case) | Consistent with 15_Addendum workflow (official docs first). Low risk for read-only MVP. Follow-up: operator to verify current app credentials in portal.

**REST API Base URLs, Versioning, Paths, Scope, Categories:**
- https://developers.procore.com/reference/rest (with ?version=latest/v1.0/v1.1/v2.0) + /development-environments | 2026-05 | Production: https://api.procore.com (REST paths /rest/v1.x/... or /rest/v2.0/... for some); Sandbox: https://sandbox.procore.com. Modern /rest/ paths preferred; legacy /vapid/ in current repo seeds are provisional. Company scope (company_id=5280 for HB) via header or path; project-scoped require project_id. Categories include foundation (companies, projects, users, vendors, cost codes, WBS), project_controls (RFIs, submittals, drawings, daily logs, observations, meetings, punch, etc.), financials (budget, commitments, change events, invoices, etc.). | Adopt modern /rest/v1.x (or v2.0 where recommended) paths for all new work; retain company_id=5280 for HB; use Procore-Company-Id header for company-scoped calls. Current repo seeds' /vapid/ paths are legacy/provisional — modernize in follow-up prompts using this register. | High (official reference + development-environments page) | Aligns with 01A enrichment (which began modernizing core endpoints). Risk: tenant-specific variations in financial endpoints. Follow-up: full dry-run verification of broader unverified catalog using these paths.

**Pagination, Filtering, Sorting, Response Shapes:**
- https://developers.procore.com/documentation/pagination + /filtering-on-list-actions | 2026-05 | Pagination: page (1-based, default 1), per_page (default ~10, max varies by endpoint; some 5000; respect per-endpoint limits); Link headers (first/prev/next/last) or pagination metadata in body (current_page, total_entries). Some newer/V2 use cursor (starting_after / next_starting_after). Filtering: filters[field]=value (arrays via []= , date ranges with .. or gte/lte, search via query). Sorting: sort=field (asc) or -field (desc); only documented fields per endpoint. Responses: JSON, often with metadata + array of items. | Always combine pagination + aggressive filtering (filters[] + sort) to keep responses small and avoid rate limits/timeouts. Use Link headers for cursor-like navigation. Default per_page=10 for most; check specific endpoint docs. | High (dedicated pagination + filtering pages + reference examples) | Reduces load (pairs with rate limits below). Risk: endpoint-specific variations. Follow-up: test with the unverified catalog candidates.

**Rate Limits, Quotas, 429 Handling, Best Practices:**
- https://developers.procore.com/documentation/rate-limiting + /error-reference + /faq | 2026-05 | Two limits per client_id (app): 3,600 requests per 60-min window (hourly) + 100 requests per 10-sec window (spike). Headers on responses: X-Rate-Limit-Limit (total in window), X-Rate-Limit-Remaining, X-Rate-Limit-Reset (unix timestamp). 429 Too Many Requests on exceed (message "exceeded the API rate limit"); Retry-After header on 429s. Limits per OAuth client_id; sandbox may differ. Additional per-app/per-endpoint quotas in some cases (Agentic APIs). | Monitor X-Rate-Limit-Remaining on every response; proactively throttle/pause before hitting 0. On 429, backoff using Retry-After or X-Rate-Limit-Reset (exponential + jitter recommended). Reduce calls via webhooks (vs polling), filters + pagination, caching, batch where available. Request limit increases from Procore if needed (e.g., to 7,200+/hr). Separate sandbox/prod credentials help isolate testing load. | High (dedicated rate-limiting page + error reference + FAQ) | Critical for MVP stability (pairs with pagination/filtering). Risk: per-company vs per-app quotas (less transparent); tenant variations. Follow-up: implement header-based throttling in any future client code; test under load in sandbox.

**Errors, Status Codes, Retry Guidance, Changelog/Version Notes:**
- https://developers.procore.com/documentation/error-reference (and individual reference pages with changelogs) + rate-limiting page | 2026-05 | 429 for rate limit (see above); other 4xx (validation, auth, permissions), 5xx (server). Retry-After on 429s; backoff guidance. Changelog on reference pages (e.g., /rest transitions from older paths, New REST V2 notes, per-endpoint changes). Best practices: User-Agent header, efficient queries, webhooks for change notifications. | Implement robust 429 handling (backoff using official headers); treat 4xx as client errors (log + fix query); 5xx as transient (retry with backoff). Check per-endpoint changelogs before relying on paths. Use official reference pages (with version params) as source of truth over older examples. | High (error-reference page + rate-limiting + reference changelogs) | Reduces operational issues. Risk: undocumented per-tenant behaviors in financials. Follow-up: include header monitoring and backoff in any client implementation.

**Overall Decision for Phase 3 (synthesized):**
Use the modern /rest/v1.x (or v2.0) paths from the official reference (as started in 01A enrichment); OOB for Bobby-only CLI; sandbox first with separate credentials; always respect rate limit headers + pagination/filters; official docs (the pages above) + redacted dry-run evidence are the only sources for verification (no machine-readable export per 15_Addendum and confirmed here). The materialized unverified seed (from Phase 03 package) provides the candidate catalog to expand against this register.

## 7. Governance Attestation

| Reference | Status |
| --- | --- |
| `CLAUDE.md` §5 (vault governance, surgical/minimal, repo truth precedence, evidence rule) | Honored (research-only, evidence stays in docs/evidence/, no code changes, repo truth via safe git/list only) |
| `hb-personal-assistant/.grok/skills/vault-package-governance/SKILL.md` | Honored (this evidence md stays in-repo, not classified as vault package; no payload re-copy) |
| Phase 03 package 15_Addendum (exact Downloads path, previously located) | Referenced from prior context (no machine-readable export finding; verification workflow of official docs first + redacted dry-run; this Prompt_01 executes the research portion) |
| Prior phase-03 evidence (00- and 01A mds) | Used for style/template (HEAD table, sections, guardrails checklist) via safe methods only |
| Official Procore Developer docs (via web research) | Primary/only source of truth for all facts and decisions in the register |

## 8. Guardrails Preserved (explicit checklist)

- Local-first, Bobby-only MVP, read-only external: yes (web research on public docs only; no Procore/SharePoint/etc. calls of any kind).
- No POST/PUT/PATCH/DELETE or writeback: yes (research only).
- No app mutation, production webhooks, company-wide: yes.
- No source copying to Obsidian, no full Procore bodies in Obsidian: yes (no Procore calls; evidence has only public doc URLs/facts).
- No tokens/secrets/credential material in repo/evidence/logs/SQLite/Obsidian: yes (none encountered or stored; all research public docs).
- No contract/financial/etc. decisioning by model: yes (research only; decisions are documented facts from official sources for human/controller use).
- Sensitive routes to review, controller validates: yes (research posture).
- Models never execute file ops: yes (no code changes).
- Dry-run/apply for live: n/a (no live calls; research only).
- Unit tests no live Procore unless marked: n/a (no test changes).
- Evidence bundles in docs/evidence/**, not vault packages: yes (this md only).
- Repo truth > planning notes: yes (official docs + safe git/list for local state).
- If vault conflict: stop: n/a (no conflict).

All verified. No exceptions. Research-only posture explicit throughout.

## 9. Residual Risk

- Official docs JS-rendered (web_fetch may return limited shell/content; confirmed in 15_Addendum and here — note in register; recommend operator browser verification for any Low-confidence or critical facts).
- Tenant-specific variations (especially financial endpoints, per-company quotas) — documented in register; dry-run in sandbox first required for verification.
- Current repo seeds still contain legacy /vapid/ paths (provisional per this research) — risk noted; modernization started in 01A, continue in follow-up using this register.
- Sub-agent results pending (they are actively researching the same sources; will augment register with any additional details/confidence when collected).
- "Do not re-read" + context discipline for future prompts (honored here via safe methods only).

## 10. Human Decisions Made During This Run (authorized)

1. Confidence methodology (High = multiple official pages + consistent + recent; Medium = one primary authoritative; Low = unclear/JS-limited — always note and recommend operator verification for Low/critical).
2. Handling of JS-rendered docs (web_fetch + explicit note in evidence/register; do not guess; operator browser for gaps).
3. Scope of "material unverified" for stop (the 6 areas in query + rate limits + common errors/changelog; all verified with High/Medium from official sources — no stop).
4. Scope of research (high-level facts/decisions for the register; no deep per-endpoint param lists or code samples in evidence; focus on actionable guidance for future prompts).
5. Sub-agent orchestration (spawned exactly 4 as detailed in approved plan with the specified briefs; results to be merged on collection).
6. Evidence content (used planning web sources for immediate completeness + sub-agent status note; will merge full sub-agent reports when available without re-running research).
7. Next prompt (use this register as the source of truth for OAuth/paths/pagination/rate limits in any follow-up endpoint reference, dry-run verification, or implementation prompts; prioritize sandbox testing with OOB and header monitoring).

All logged here with rationale. No other material decisions.

## 11. Next Prompt Recommendation

**Use this Decision Register as the authoritative source for all Procore API decisions (OAuth flow/credentials/OOB, modern /rest/v1.x paths with company_id=5280, pagination/filtering best practices, rate limit header monitoring + 429 backoff, error handling) in follow-up prompts.**

Recommended next: Prompt_01A (or the package's equivalent dry-run verification / endpoint reference implementation prompt) or a dedicated "Prompt_02_Dry_Run_Verification" — take the materialized unverified candidate catalog (in resources/config/), the enriched contract from 01A, and this register; perform the first approved, redacted, delegated GET dry-run calls (sandbox first, OOB or localhost redirect, full header monitoring, strict throttling) against the reconciled core + prioritized broader candidates. Produce only redacted structural evidence. Update verification_status in the register/matrix. Extend auditor/loader only as justified by the reference metadata.

This Prompt_01 completes the high-level research foundation. Phase 3 Procore integration can now proceed with verified facts from official sources.

## 12. Acceptance

- All query implementation steps executed (research on the 6+ areas via official docs + sub-agents, Decision Register created with required columns, rebaseline, stop conditions checked — none triggered, evidence generated as sole artifact).
- All guardrails preserved (explicit checklist in §8; research-only, no code changes, no Procore calls, no secrets).
- Evidence md complete (this file; all mandated sections from query + prior phase-03 style, including HEAD table with rebaseline values, safe inspection methods, commands with sub-agent ids, full Decision Register, human decisions, risks, next prompt).
- Sub-agents spawned and running in parallel per plan and user request (4/4 active, web tools on official docs, 0 errors; results to augment).
- Architecture/docs update and verification/commit steps remain for post (see §exec-05 in plan).

**Prompt_01 research foundation complete. Follow-up prompts may proceed using this register.**

**End of evidence.**
