# 19 Prompt Dependency Map

Execute prompts in order.

1. Prompt 00 rebaselines repo truth and stops on drift.
2. Prompt 01 applies V43 additive schema migration and fixes schema tests.
3. Prompt 02 introduces review service contracts.
4. Prompt 03 adds store methods and fixes review event insert drift.
5. Prompt 04 implements list/show/summary CLI.
6. Prompt 05 implements accept/ignore/reject CLI.
7. Prompt 06 implements snooze/edit/export/batch.
8. Prompt 07 adds targeted service and CLI tests.
9. Prompt 08 strengthens no-raw/no-writeback proofs.
10. Prompt 09 updates docs/runbooks/evidence.
11. Prompt 10 performs final validation and closeout.

Do not skip Prompt 00 or Prompt 03.
