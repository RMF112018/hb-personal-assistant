# Command Matrix

| Command | Requires Graph Consent | Mutates Local State | Expected Use |
|---|---:|---:|---|
| `hb-assistant --version` | No | No | Smoke/version check |
| `hb-assistant diagnostics env --json` | No | No | Safe environment proof |
| `hb-assistant diagnostics paths --json` | No | May ensure dirs | Path readiness |
| `hb-assistant diagnostics scan-sensitive --repo . --json` | No | No | Security proof |
| `hb-assistant auth status --json` | No | May read cache | Auth state classification |
| `hb-assistant auth login --json` | Yes for success | Writes token cache | Post-consent proof only |
| `hb-assistant diagnostics graph --safe --json` | Yes for success | No | Graph proof |
| `hb-assistant diagnostics proof delegated-graph --json` | Yes for success | Evidence only | Final delegated proof |
| `hb-assistant actions extract --dry-run --json` | No | No | Local action preview |
| `hb-assistant actions extract --json` | No | Yes | Local action persistence |
| `hb-assistant search "query" --json` | No | No | Local retrieval |
| `hb-assistant files sample --json` | No | No/fixture only | Synthetic sample |
| `hb-assistant files ingest --dry-run --json` | No | No | Provenance-backed preview |
| `hb-assistant run morning --dry-run --json` | No | Ledger/evidence may write | Main local validation |
