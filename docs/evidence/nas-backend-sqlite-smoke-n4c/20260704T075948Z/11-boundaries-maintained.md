# 11 — Boundaries Maintained

| Boundary | Status |
|---|---|
| Live Mac DB not mutated | **Held** |
| N3 NAS DB not recopied/replaced | **Held** |
| NAS-local SQLite path only (no SMB mount) | **Held** |
| No secrets copied | **Held** |
| No auth/security contents copied | **Held** |
| No vault writes | **Held** |
| No source ingestion | **Held** |
| No schedulers/watchers enabled | **Held** — `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1`; `/health` confirms disabled |
| No Cloudflare | **Held** |
| No Tailscale Serve/Funnel | **Held** |
| No router/firewall changes | **Held** |
| No Portainer restart | **Held** |
| No passwordless Docker sudo restored | **Held** |
| Operator-mediated sudo only | **Held** |
| Backend not left running | **Held** — `compose down` |
| No N5/cutover | **Held** |
| No push | **Held** |
| Docker daemon restored | **Held** — `dockerd.json.bak.n4c-20260704T075948Z` |

## Build-time deviation (documented)

`docker build --network host` used **only for image build** to resolve PyPI DNS. Runtime used standard bridge + loopback publish — not host networking.

## Container authorization

Single `hb-personal-assistant-backend` container for bounded N4C smoke only; no unrelated containers started.
