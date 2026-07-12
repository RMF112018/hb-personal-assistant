# 13 — Watcher bootstrap & trust

Watcher activation, its non-circular relationship to bootstrap, and its consumption of the shared trust
authority are documented in **[13-watcher-bootstrap-noncircular.md](13-watcher-bootstrap-noncircular.md)**
and **[14-a2-corrective2-watcher-and-read-contract.md](14-a2-corrective2-watcher-and-read-contract.md)**.
The A4 addition — an unresolved quarantine blocks `safe_for_watcher_activation` — is proven end-to-end in
`tests/test_source_index_quarantine_lifecycle.py` (see **[05-a4-quarantine.md](05-a4-quarantine.md)** and
**[15-final-cumulative-validation.md](15-final-cumulative-validation.md)**).
