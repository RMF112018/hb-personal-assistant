# P06 — Connections UI Cards and Workflows

Implement connection UI.

Add/refactor:
- Source Connections panel;
- Graph/Microsoft 365 connection card;
- Procore connection card;
- shared status/action components.

Each card must show state, last local update, local/mock mode, auth/config/mapping warnings, and available actions. Live refresh must be disabled or confirmation-gated.

Tests must cover connected, stale, missing-auth, missing-config, missing-mapping, local-mode, error, and disabled-live states.
