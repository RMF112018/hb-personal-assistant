# Real API Driver Route Proof

**STAMP:** 20260701T075049Z  
**Proof type:** real local DB + real API

## Results

| Check | Status | Artifact |
|-------|--------|----------|
| Query route `activity_id=FAB/DEL-10` | **200**, `available: true` | `api-driver-query-fab-del-10.json` |
| Decoded activity_id | `FAB/DEL-10` | redacted artifact |
| Named `baseline_context` | `current_contract_baseline` | redacted artifact |
| Legacy path `FM-PERMPOWER` | **200** | `api-driver-legacy-nonslash.json` |
| Invalid basis | **400** `invalid_comparison_basis` | `api-driver-invalid-basis.json` |
| Conflicting basis | **400** `conflicting_comparison_params` | `api-driver-conflicting-basis.json` |

## Full captures (local only)

Full JSON with schedule movement details stored under:

`local-raw/*.full.json` (gitignored path — not committed)

Committed artifacts are redacted summaries. Full captures (local only):

| File | SHA256 |
|------|--------|
| `local-raw/api-driver-query-fab-del-10.full.json` | `2f8e5bdc8e8c2830032101e0d99cc01fc104a39c0726046beeb5d4635ae811bd` |
| `local-raw/api-driver-legacy-nonslash.full.json` | `b3316501e3d1b69d43fbfee7369cd572d80edb3a18fb720880af82e7b5e9afcf` |
| `local-raw/api-driver-invalid-basis.full.json` | `20f18302a8ab418cf48101ead5626fcb887a27060d7d8001abbcda2ac97a0c81` |
| `local-raw/api-driver-conflicting-basis.full.json` | `5c2566dfcc07f546379f092cdf7f074bdb42f77f524ace93e78220d7d8b92122` |

## Phase 10 regression closed

`GET .../drivers/FAB%2FDEL-10/detail` previously returned MCP **401**; query route returns **200** with named baseline context.
