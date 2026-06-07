# 16 Evaluation and Golden Fixtures Plan

## Required metrics

- task extraction precision;
- task extraction recall;
- commitment extraction precision;
- commitment extraction recall;
- relationship candidate acceptance rate;
- false positive rate;
- false negative rate;
- human acceptance rate;
- model latency;
- model timeout/fallback rate;
- schema validation failure rate;
- stale task reduction;
- follow-up closure time;
- source-ref completeness.

## Fixture families

- email request to user;
- email commitment by user;
- unresolved follow-up;
- waiting-on-others thread;
- meeting prep candidate;
- Procore RFI/change/status signal;
- Obsidian note update;
- Claude MCP packet.

## Evaluation rule

Do not optimize solely for recall. In this product, false positives that nag the user are costly. Default to reviewable candidates and suppression tooling.
