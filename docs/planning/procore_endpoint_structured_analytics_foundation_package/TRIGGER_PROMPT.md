You are working with Bobby on the `RMF112018/hb-personal-assistant` repository.

Execute the objective defined at:

`docs/planning/procore_endpoint_structured_analytics_foundation_package/README.md`

Important correction: this is not simply for the local daily brief agent/model. Bobby will use Procore data for future analytics. The primary objective is durable local Procore endpoint data capture in structured, endpoint-appropriate database tables. Daily brief/local-model usefulness is a downstream consumer and validation target, not the owner of the storage design.

Follow the README exactly. Execute the prompt sequence in order. Obey all hard constraints and stop conditions. Do not perform external writeback. Do not mutate the production DB during audit/validation. Use SQLite `.backup` copies for DB inspection and migration tests. Do not commit raw payloads or DB extracts. Produce the required evidence and final handoff.
