# Stop Conditions

Stop and report if:

1. The active branch is not the intended branch and cannot be safely corrected.
2. The repo already has a conflicting implementation for modified-by metadata.
3. The canonical drive item table cannot be identified.
4. The schema/migration path is ambiguous.
5. A destructive migration would be required.
6. Graph drive item payloads do not expose `lastModifiedBy` and no safe fixture can validate the path.
7. Implementation would require Graph writeback.
8. Implementation would require exposing raw file/user metadata in committed artifacts.
9. Production DB mutation would be required without Bobby approval.
10. Tests reveal unrelated failures that obscure validation and cannot be isolated.
