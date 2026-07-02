# Phase 20 Rollout Checklist

1. Generate Phase 19 schedule notes (`obsidian_schedule_review_notes.py`) — dry-run first.
2. Run graph discovery dry-run:
   `python scripts/obsidian_schedule_note_graph.py --vault-path "$VAULT" --project-key tropical`
3. Review `05-graph-dry-run.md` for recommended candidates and tag recommendations (report-only).
4. Optional: `--suggest-links --confirm-local-llm` for Qwen report-only suggestions.
5. Fixture/evidence apply only:
   `--apply-links --confirm-graph-apply --evidence-dir <evidence>`
6. Re-run Phase 19 note refresh; confirm `hb-schedule-graph` block unchanged (`13-phase19-rerun-graph-preservation.txt`).
7. Live vault: dry-run only until separate live-vault approval.
