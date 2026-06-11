# 02 — Target Commit Basis

## Audit / implementation basis

- Commit basis (README): `4d8ca0717324955dab539ebf0690b5a93d4db6e0`
- Subject: `Merge pull request #22 from RMF112018/fix/email-calendar-full-raw-content-ingestion`
- This merge landed the V49 email/calendar full raw-content ingestion + structured projection layer (the substrate this slice activates).

## Recent history (basis and ancestry)

```
4d8ca071 Merge pull request #22 ... email-calendar-full-raw-content-ingestion
97b615a5 fix(email-calendar): map calendar locations[] address/coordinates nested fields (244 v1)
eb376b64 Merge pull request #21 ... procore-scheduled-freshness-taxonomy
fe1c44b5 fix(scheduler): harden scheduled Procore refresh against FD exhaustion (243 v1)
1343b53e fix(procore): precise raw-payload freshness taxonomy for scheduled refresh (242 v2)
7e23e31e docs(evidence): capture construction intelligence proof updates
cb19d33e docs(email-calendar): resolve handoff SHA + correct read-model precedence wording (Pass 2 cleanup)
7a663951 feat(email-calendar): consumer read-model rewiring to structured projections (Pass 2)
```

## Confirmation

The local repository is exactly at the target basis (HEAD == main == origin/main == `4d8ca071`). No divergence to reconcile. The substrate referenced by the follow-up audit (V49 projection engine, candidate writer, gates, Procore raw payloads) is present at this basis; this slice activates and gates it.
