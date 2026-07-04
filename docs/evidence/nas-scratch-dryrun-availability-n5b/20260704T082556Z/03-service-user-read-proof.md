# 03 — Service-User Read Proof

Run as `personal-assistant-svc` (via `bfetting` sudo). Read/stat only — no writes, no `syn-work` enumeration.

## Vault read (NAS mirror)
```
svc_vault_dir=yes
svc_vault_md_count=155
```
The demoted service user can traverse the mirror and enumerate all **155** markdown notes — matching source and the
N5A proof. Read access confirmed without any write.

## `syn-work` bounded read
```
svc_synwork_dir=yes
svc_synwork_NAS_HB=yes
svc_synwork_Altman=yes
svc_syn_work_top_segments=yes
```
The service user can stat `/volume1/homes/bfetting/Work` and its two known top-level segments (`NAS - HB`, `Altman`).
This confirms `syn-work` is **reachable and readable by svc** (traverse chain via the mode-777/others-r bits, not a
dedicated ACL). No full enumeration was performed. **No write was attempted against `syn-work`.**

## Scratch config read (service user)
```
svc_can_read_scratch_config=yes
```
The service user can read the non-active scratch config placed under the scratch root (see `04`).

## Significance
These are the authoritative **NAS-target** availability proofs (the repo probe in `06` ran against the local
byte-equivalent vault because the NAS path is not locally mounted). Together they satisfy the "at least one safe
stat-only availability proof runs successfully" acceptance bullet — on the real NAS target.
