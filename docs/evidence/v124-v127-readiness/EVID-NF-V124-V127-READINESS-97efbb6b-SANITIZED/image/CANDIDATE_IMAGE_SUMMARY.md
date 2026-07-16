# image/CANDIDATE_IMAGE_SUMMARY.md — SANITIZED (public tier)

Replaces (for the public tier) the raw candidate-image inspect/build/load logs (retained private-only). The hashed
Docker image **archive** itself is private (operator instruction, EVID-AUD-007).

## Candidate image identity (opaque digests)
- Repo:tag `hb-personal-assistant:v127-candidate-97efbb6b`
- Multi-arch index digest: `<candidate-index-digest>` · amd64 manifest: `<candidate-amd64-manifest-digest>` ·
  amd64 config: `<candidate-amd64-config-digest>`
- Platform: linux/amd64 · Revision label: `97efbb6bc4992e26c0d07a3735256fd98d77461b` (public git SHA — the subject)
- Code proof: `LATEST_SCHEMA_VERSION=127`; contains the NF-F-001 migration-authorization modules
- Build: `docker buildx build --platform linux/amd64` from a git-archive context of `origin/main` at 97efbb6b

## Preservation (private artifact)
A hashed Docker image archive of this candidate is retained in the private evidence store, offline-integrity-verified
(all manifest-referenced blobs present + hash-matched). See `PRIVATE_EVIDENCE_REFERENCES.md` for its receipt IDs + SHA-256.

## Finding
NF-IMG-001 (Medium, OPEN): the archive proves durable candidate retention bound to 97efbb6b, but the **final
deployment artifact identity is NOT VERIFIED** (no registry repository digest; no registry push this phase).
