# 06 Ranked Signals, Candidates, And Downstream Consumers

This package keeps daily brief/local-model behavior downstream of the structured analytics layer.

Ranking diagnostics from the copied DB:

- Open Procore signals: `5,866`.
- Due-soon signals for `2026-06-10`: `0`.
- Aggregate-sludge signals: `5,476`.
- Closed-record open signals: `158`.

Projection rule: suppress aggregate sludge unless a specific record has due/recent/owner/materiality
or safety evidence. Closed records should not generate open brief priorities without unresolved
follow-up evidence.
