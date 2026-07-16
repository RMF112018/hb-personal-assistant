# PRIVATE_EVIDENCE_REFERENCES — pointers to private-tier evidence (by ID + SHA-256 only)

- classification: Audits (supporting evidence)
- version: 6.0 · created_utc: 2026-07-16
- The public tier references private evidence **only** by {artifact ID, SHA-256, trust, bounded claim}. No private
  storage paths, no raw values, no redaction map. The private evidence store is access-restricted (700), not
  Git-tracked, and holds the raw topology, receipts, authorization record, and Docker image archive.

| Artifact ID | SHA-256 | Trust | Bounded claim it supports |
|---|---|---|---|
| DECISION-NF-V124-V127-REMEDIATION-AUTH-001 (authorization record) | `98ccb138ec359d71ac05fd52fb9df5930da54a356a54916e8f2ea4cd3d6a0684` | trusted | Operator AUTHORIZED WITH CONDITIONS: local commit 89c745d2, sanitized successor from 97efbb6b, image retention, prior load, rebuilt-closure-as-successor |
| verbatim-operator-answers | `b2eed18ebd45fb65b073e82b72696f56ee705988037a9188136b557f92f1e313` | trusted | Verbatim source of the ratification + NAS-receipt policy + image policy |
| STAGE0-PREFLIGHT | `a1902b2e14fc50a6079abd5ba9b494807aa46a53944f1f2ff73df8093655b38a` | trusted | Stage-0 baseline + stop-condition evaluation (none tripped) |
| IMG-EXPORT-V127-97efbb6b-amd64 (export receipt) | `867eb3c9871c1de6e2ba6491dc0b5f26c33827bd6b315686762b06bad3d2692a` | trusted | Candidate image exported to a hashed Docker image archive bound to 97efbb6b |
| IMG-VALIDATION-V127-97efbb6b-amd64 (reload validation) | `820ca9e14db0c889d34a3440beef9d5e5630086d6eedcf174d09a3388e9e50e1` | trusted | Archive metadata integrity PASS (15/15 blobs); reloadability + final identity NOT VERIFIED |
| docker-image-archive (Docker save format) | `e832fcbb8884d7d87ab876c870055adb4db14876308d4648d59b023f0f809672` | trusted | The retained candidate image bytes (private-only; size retained privately) |
| command-receipts/README | `8f0e29a49d159e0e5dbb30cd9c3b1ffa9bc56fb444e7a4f8dcd3d60d85cd7ee2` | trusted | Receipt coverage rule + classification |
| command-receipts/RECEIPTS | `7ea8f6897f363158619333e5d9d5dea25b8100297d8fc10728708dd82332adcc` | partially_trusted | Reconstructed NAS + material-local receipts; trusted current-op receipts |
| PRIVATE_REDACTION_MAP | (private; hash recorded in private manifest) | trusted | Raw→placeholder map used by the publication gate (never public) |
| PRIV-EVID-V124V127-REH-13 (rehearsal backup/restore raw) | `06986137baba443715dc79110a4421a9f6a3bfe103b0ba4614a0aa988b23f637` | partially_trusted | Raw capture behind the 13 backup/restore proof (moved private in v5) |
| PRIV-EVID-V124V127-REH-13B (rehearsal receipt-gating raw) | `7e9a25506b36258d774dd76c10dde2dd4c8fa88128396158505ddfe7191fd0b5` | partially_trusted | Raw capture behind 15 receipt-gating (moved private in v5) |
| PRIV-EVID-V124V127-REH-14 (rehearsal migration-run raw) | `6223ef8e97708afe41fefa33cee561b932788e4ccc3eca66cd24186f7466d468` | partially_trusted | Raw run log behind 14 V124→V127 migration rehearsal (moved private in v5) |
| PRIV-EVID-V124V127-REH-15 (rehearsal failure-atomicity raw) | `48232e4e487a1fffd172035eef5b8196d64f6b456025f8f7197dec9e4a885a38` | partially_trusted | Raw capture behind 15 failure/atomicity rehearsal (moved private in v5) |
| PRIV-EVID-V124V127-REH-15B (rehearsal rollback-injection raw) | `eb752122a723433bc3c660e4b85899c5dba23128e0ba8a1ac7f3722ff2ea71c2` | partially_trusted | Raw capture behind 15 atomicity rollback injection (moved private in v5) |
| PRIV-EVID-V124V127-REH-16 (rehearsal post-migration raw) | `8c984ad300700b4a8918d8b3ffae2c5740fa5d28b80ac4d3acbb7d70f05dbb43` | partially_trusted | Raw capture behind 16 post-migration validation, V127 after (moved private in v5) |
| PRIV-EVID-V124V127-REH-PRE (rehearsal pre-migration raw) | `9d6bae32ec229e9404df055fe24fdf686636bc6b75e3ff3aff80ca7a3b1eafe3` | partially_trusted | Raw capture behind 16 pre-migration V124 before-state (moved private in v5) |
| PRIV-EVID-V124V127-RUNTIME-INSPECT (container inspect raw) | `4c1b2ed156f5f84505d88247939c17b3c6446fbf3625b7def6d20998ba195cdb` | partially_trusted | Raw deployed-container inspect behind the bounded DEPLOYED_RUNTIME_SUMMARY (private in v5) |
| PRIV-EVID-V124V127-RUNTIME-LOGS (running-container log tail raw) | `9de308f89b689631aba1af051b4af9ef2bcf3024ce9ddadaf901c5a6b6910484` | partially_trusted | Raw running-container log tail / auth flow behind the runtime summary (private in v5) |
| PRIV-EVID-V124V127-RUNTIME-IMGINSPECT (running-image inspect raw) | `8c8e3fbd1313da320c94193dc8d3cf7391dea5e5c1e7c50d2f686c80eec3af4b` | partially_trusted | Raw running-image inspect behind the runtime summary (private in v5) |

Note: the private package's own MANIFEST + reconstruction receipt (generated at packaging) provide the complete
private-tier hash index. This public list is the minimal cross-reference needed to trace public claims to private
evidence.
