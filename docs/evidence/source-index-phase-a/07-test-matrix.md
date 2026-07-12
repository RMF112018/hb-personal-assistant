# A0 — Test-Design / Node-ID Matrix (Phase A)

Design only. Prove-red tests are **introduced per sub-phase** and run against that sub-phase's parent commit
(prove-red evidence captured to the package), then implemented and committed green. Node IDs below are the
planned identifiers; each row names the behavior it certifies and the parent commit it must prove-red against.

## A1 — `tests/test_source_index_vault_deletion_safety.py` (prove-red vs A0 commit)
| Node ID | Behavior certified |
|---|---|
| `test_vault_over_cap_does_not_delete_unseen_notes` | Cap-hit (truncated) scan reconciles zero deletions |
| `test_vault_truncated_scan_does_not_delete` | `truncated=True` blocks reconcile |
| `test_vault_directory_read_error_does_not_delete` | `error_sink` non-empty ⇒ no delete |
| `test_vault_root_unavailable_does_not_delete` | Missing/unavailable root ⇒ no delete |
| `test_vault_interrupted_scan_does_not_delete` | Interruption before exhaustion ⇒ no delete |
| `test_vault_complete_scan_deletes_confirmed_absent_note` | Certified-complete scan reaps a genuinely absent note |
| `test_vault_complete_scan_preserves_present_notes` | Present notes never deleted |
| `test_vault_false_delete_does_not_remove_fts` | Uncertified scan leaves FTS intact |
| `test_vault_false_delete_does_not_stale_generated_card` | Uncertified scan does not stale cards |
| `test_vault_confirmed_delete_updates_source_fts_and_card_state_atomically` | Confirmed delete: row+FTS+card in one txn |
| `test_vault_scan_remains_streaming_and_prunes_excluded_subtrees` | Still `os.scandir` streaming; no `rglob` |
| `test_vault_scan_is_idempotent_after_resume_or_retry` | Re-run stable |
| `test_vault_empty_completed_scan_blocks_mass_delete` | Empty-observation blast-radius guard blocks mass delete |
| `test_vault_confirmed_empty_recovery_requires_fresh_selfscan` | Operator recovery performs its own scan; rejects caller-supplied result |

## A3 — `tests/test_source_root_mapping.py` (prove-red vs A1 commit)
Adversarial corpus: `work, syn-work, work-backup, backup-work, home, home-work, vault, vault-backup, project, projects`.
| Node ID | Behavior certified |
|---|---|
| `test_exact_match_succeeds` | Exact normalized key resolves |
| `test_valid_configured_map_succeeds` | Configured `structure_root_map` resolves |
| `test_invalid_explicit_map_fails_closed` | Nonexistent target ⇒ `invalid_explicit_map`, not-ready |
| `test_work_does_not_match_syn_work` | No prefix-strip collision |
| `test_work_does_not_match_work_backup` | No substring collision |
| `test_home_does_not_match_home_work` | No substring collision |
| `test_health_and_bootstrap_agree` | Same resolution both paths |
| `test_health_and_watcher_readiness_agree` | Same resolution both paths |
| `test_unmapped_root_cannot_be_structure_ready` | `unmapped` ⇒ not structure-ready |
| `test_resolver_exception_cannot_produce_ready_state` | Fail-closed on exception |
| `test_no_absolute_paths_in_serialized_responses` | No path leak |
| `test_cli_override_precedence_and_provenance` | `cli_override` > configured > exact; provenance tagged |
| `test_ephemeral_override_cannot_certify_durable_readiness` | `mapping_override_not_persisted` guard |
| `test_duplicate_keys_after_normalization_rejected` | `ambiguous_configuration` within-source only |
| `test_many_to_one_allowed_unless_repo_prohibits` | Many-to-one not auto-rejected |

## A2 — `tests/test_source_root_trust.py` + updates (prove-red vs A3 commit)
| Node ID | Behavior certified |
|---|---|
| `test_explicit_stale_root_search_fails_closed` | `blocked_root_unready`, zero items |
| `test_explicit_partial_root_search_fails_closed` | Partial gen ⇒ blocked |
| `test_explicit_failed_generation_search_fails_closed` | Failed gen ⇒ blocked |
| `test_running_corrective_generation_does_not_reopen_trust` | Running ≠ safe |
| `test_policy_stale_root_returns_no_authoritative_items` | Policy-stale ⇒ blocked |
| `test_unscoped_search_excludes_unsafe_roots` | Unscoped restricts to safe roots |
| `test_unscoped_search_discloses_excluded_roots` | `excluded_root_keys` + reasons |
| `test_safe_root_search_remains_functional` | Safe root still returns items |
| `test_metadata_unsafe_root_blocked` | Unsafe metadata blocked (no advisory) |
| `test_configless_root_is_unverified_not_authorized` | `authorization_state=unverified` |
| `test_configless_sensitivity_unknown_not_false` | `sensitivity=unknown` |
| `test_search_does_not_claim_live_readability_without_probe` | No `live_readable`; `live_readability=unverified` |
| `test_exact_read_absent_file_returns_explicit_absent` | `verified_absent`/denied, not success-like |
| `test_exact_read_checks_root_trust_before_fs` | Trust checked before FS |
| `test_sensitive_root_cannot_be_live_read` | Sensitive fail-closed |
| `test_aggregate_health_any_vs_all` | `any_root_safe` ≠ `all_enabled_roots_safe` |
| `test_zero_authorized_roots_is_not_client_safe` | Non-vacuous all-safe |
| `test_root_specific_health_matches_source_operations` | Health == serving decision |
| `test_source_watcher_start_rejects_unsafe_roots` | `start()` enforces readiness |
| `test_direct_and_gateway_return_equivalent_trust` | Parity |
| `test_prompt_routing_does_not_bypass_readiness` | Routing respects trust |
| `test_no_absolute_path_leaks` | No path leak |
| `test_safe_root_pagination_deterministic` | Pagination stable |
| `test_read_status_legacy_field_not_contradictory` | No `live_readable` alongside `unverified` |

## A4 — `tests/test_source_index_quarantine.py` + update `..._generation_hardening.py:524` (prove-red vs A2 commit)
| Node ID | Behavior certified |
|---|---|
| `test_persistent_stat_failure_retries_up_to_threshold` | Bounded retries |
| `test_threshold_transition_creates_one_quarantine_row` | One row at threshold |
| `test_repeated_passes_do_not_duplicate_quarantine_rows` | Idempotent |
| `test_cursor_advances_after_quarantine` | Forward progress |
| `test_later_files_are_indexed` | Poison doesn't block successors |
| `test_generation_not_completed_while_quarantine_remains` | Non-authoritative |
| `test_reconciliation_blocked_while_quarantine_remains` | No unsafe reconcile |
| `test_root_trust_reports_quarantine_blocker` | Trust reason code |
| `test_transient_error_before_threshold_never_quarantines` | No premature quarantine |
| `test_later_successful_retry_resolves_quarantine` | Resolution path |
| `test_resolved_quarantine_permits_progress` | Clean pass completes |
| `test_crash_and_resume_preserve_quarantine_and_cursor` | Durable |
| `test_lease_loss_does_not_corrupt_quarantine_ownership` | Ownership-safe |
| `test_concurrent_retry_is_idempotent` | Concurrency-safe |
| `test_error_detail_contains_no_absolute_path` | Redaction |
| `test_sensitive_root_errors_remain_redacted` | Redaction |
| `test_migration_v125_fresh_safe` | Fresh DB |
| `test_migration_v125_upgrade_safe_and_idempotent` | Upgrade + rerun |
| `test_config_threshold_validation` | Validated threshold |
| `test_policy_fingerprint_changes_on_quarantine_policy_change` | Correctness participates in fingerprint |
| `test_cli_list_and_retry_are_bounded` | Bounded CLI |
| `test_no_remote_write_tool_introduced` | No remote write surface |
| `test_no_forward_progress_suspends_auto_retry` | `quarantine_unresolved` not auto-restarted |
| `test_confirmed_absent_only_after_live_observation` | Not absent merely because retry can't locate |
| `test_generation_retention_preserves_unresolved_quarantine` | No cascade delete |
| `test_resolved_quarantine_retention_is_bounded` | Bounded retention |
| `test_pruned_origin_generation_does_not_clear_root_blocker` | Root blocker survives pruning |
| `test_per_file_error_holds_cursor_then_retries` (UPDATED) | Retry-to-threshold, then quarantine+advance |

## FINAL — cumulative + CI
Cumulative source-index / client-trust / watcher-recovery / migration groups + failure injection + static
checks; new `.github/workflows/source-index-gate.yml`. See plan FINAL.
