# Known Limitations

- P6 XER may provide assigned baseline references but not baseline activity rows.
- P6 XML may provide baseline activity rows but may lack XER-style float/driving path fields.
- Resource assignment objects were not present in the reviewed committed fixtures.
- Cost/schedule correlation is deferred.
- CPM recalculation is not implemented in this remediation.
- Manual ZIP package evidence was produced for `TWN.zip`, `Caretta.zip`, and `BlueLake.zip`. Some individual companion-file attempts returned duplicate-version previews in the broader manual pass, which is recorded in `manual-package-proof/README.md`.
- SQLite proof databases are local verification artifacts and are intentionally not committed.
