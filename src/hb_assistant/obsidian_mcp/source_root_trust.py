"""Shared root-specific client-trust authority (A2).

ONE structured trust decision per source root, consumed identically by the health projection, the client
serving paths (search / list / metadata / bounded read), and watcher startup. Serving is **fail closed**:
an unsafe root can never return indexed file items, metadata, or a live read through any client operation.

The decision logic (:func:`evaluate_root_trust`) is a PURE function of already-gathered primitives, so
health (which batch-loads those primitives for every root) and the single-root serving loader
(:func:`load_root_trust`) reach byte-identical verdicts from one authority. There is no ``advisory`` trust
state in Phase A.

Mapping resolution and structure readiness are DISTINCT facts (A3 corrective clarification):

* ``structure_mapping_resolved`` — the canonical A3 resolver produced a structure key.
* ``structure_ready`` — OPERATIONAL: mapping resolved AND the structure backend is available AND structure
  ingestion exists (a folder map) AND the applicable structure run state is ready. A resolved mapping ALONE
  never makes a root safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .source_root_mapping import (
    REASON_CONFIG_UNAVAILABLE,
    StructureRootMapping,
    normalize_root_key,
    resolve_structure_mapping,
)

# ---- vocabularies ---------------------------------------------------------------------------------
TRUST_SAFE = "safe"
TRUST_BLOCKED = "blocked"
TRUST_UNVERIFIED = "unverified"
TRUST_DENIED = "denied"

AUTH_AUTHORIZED = "authorized"
AUTH_UNVERIFIED = "unverified"
AUTH_DENIED = "denied"

CONTENT_NONE = "none"
CONTENT_PARTIAL = "partial"
CONTENT_COMPLETE = "complete"

# Serving result states (client envelope ``status``).
RESULT_OK = "ok"
RESULT_BLOCKED_ROOT_UNREADY = "blocked_root_unready"
RESULT_UNKNOWN_ROOT = "unknown_root"
RESULT_UNAUTHORIZED_ROOT = "unauthorized_root"
RESULT_INVALID_REQUEST = "invalid_request"

# Reason codes (deterministic, path-free).
RC_ROOT_DISABLED = "root_disabled"
RC_AUTH_UNVERIFIED = "authorization_unverified"
RC_POLICY_UNCERTIFIED = "policy_uncertified"
RC_POLICY_STALE = "policy_stale"
RC_POLICY_UNAVAILABLE = "policy_unavailable"
RC_INDEX_LAYERS_UNREADY = "index_layers_unready"
RC_FRESHNESS_UNKNOWN = "freshness_unknown"
RC_SENSITIVE_ROOT = "sensitive_root"
RC_STRUCTURE_DATA_UNREADY = "structure_data_unready"
RC_STRUCTURE_MAPPING_UNAVAILABLE = "structure_mapping_unavailable"
RC_UNKNOWN_ROOT = "unknown_root"
RC_QUARANTINE_UNRESOLVED = "quarantine_unresolved"

# Watcher-startup fail-closed reason codes (sanitized, path-free). The watcher may activate a root ONLY
# when it is fully ready (bootstrapped + certified + reconciled + structure-data-ready); every other state
# maps to exactly one of these.
WATCHER_ROOT_NOT_BOOTSTRAPPED = "watcher_root_not_bootstrapped"
WATCHER_POLICY_STALE = "watcher_policy_stale"
WATCHER_RECONCILIATION_INCOMPLETE = "watcher_reconciliation_incomplete"
WATCHER_STRUCTURE_DATA_UNREADY = "watcher_structure_data_unready"
WATCHER_ROOT_DENIED = "watcher_root_denied"
WATCHER_ROOT_NOT_READY = "watcher_root_not_ready"


@dataclass(frozen=True)
class RootTrustInputs:
    """Gathered primitives for one root — the pure decision function's whole input surface."""

    root_key: str
    enabled: bool
    sensitive: bool
    has_config: bool
    backend_available: bool
    freshness_state: str
    folder_count: int
    file_count: int
    counts: dict[str, int]
    gen_row: dict[str, Any] | None
    current_fp: str | None
    file_index_status: str | None
    legacy_watcher_ready: bool
    struct_mapping: StructureRootMapping
    mapping_config_available: bool
    unresolved_quarantine_count: int = 0


@dataclass(frozen=True)
class RootTrustDecision:
    """Structured, serialization-safe trust verdict for one root. Carries NO absolute path."""

    root_key: str
    trust_state: str
    authorization_state: str
    enabled: bool
    sensitive: bool
    sensitivity_known: bool
    safe_for_path_lookup: bool
    safe_for_live_read: bool
    safe_for_content_answering: str
    policy_verification: str
    generation_status: str | None
    reconciliation_complete: bool
    structure_mapping_resolved: bool
    structure_mapping_reason: str
    structure_key: str | None
    structure_ready: bool
    index_only_available: bool
    freshness_status: str
    metadata_completeness_state: str
    content_completeness_state: str
    watcher_ready: bool
    unresolved_quarantine_count: int = 0
    reason_codes: list[str] = field(default_factory=list)

    @property
    def safe_for_client_answering(self) -> bool:
        """Whole-root client-answer safety — TRUE only for a fully trusted root."""
        return self.trust_state == TRUST_SAFE

    @property
    def safe_for_watcher_activation(self) -> bool:
        """Whether ``SourceWatcher.start()`` may activate the drain for this root.

        STRICTER than client answering: the watcher maintains a root's live index, so it must not run until
        the root is fully bootstrapped and certified (``trust_state == safe`` ⇒ authorized+enabled, policy
        current, freshness known, index layers ready), its reconciliation is complete, AND its structure data
        is ready. A resolved mapping / a bare bootstrap-state row is never enough. Bootstrap is a SEPARATE
        watcher-independent operation, so blocking the watcher pre-bootstrap creates no circular dependency."""
        return (
            self.trust_state == TRUST_SAFE and self.reconciliation_complete and self.structure_ready
        )

    @property
    def watcher_activation_block_reason(self) -> str | None:
        """The single sanitized reason the watcher must NOT activate this root, or ``None`` if it may.
        Derived from the same decision fields (no separate policy)."""
        if self.safe_for_watcher_activation:
            return None
        if self.authorization_state == AUTH_DENIED:
            return WATCHER_ROOT_DENIED
        gs = self.generation_status
        if gs is None or gs in ("failed", "abandoned"):
            return WATCHER_ROOT_NOT_BOOTSTRAPPED
        if gs in ("running", "partial", "reconcile_pending"):
            return WATCHER_RECONCILIATION_INCOMPLETE
        # gs == "completed" from here.
        if self.policy_verification == "stale":
            return WATCHER_POLICY_STALE
        if self.freshness_status == "unknown" or not self.index_only_available:
            return WATCHER_ROOT_NOT_BOOTSTRAPPED
        if not self.reconciliation_complete:
            return WATCHER_RECONCILIATION_INCOMPLETE
        if not self.structure_ready:
            return WATCHER_STRUCTURE_DATA_UNREADY
        return WATCHER_ROOT_NOT_READY

    def as_health_fields(self) -> dict[str, Any]:
        """The subset merged into the per-root health entry (preserves existing field names/values)."""
        return {
            "policy_verification": self.policy_verification,
            "index_only_available": self.index_only_available,
            "safe_for_path_lookup": self.safe_for_path_lookup,
            "safe_for_content_answering": self.safe_for_content_answering,
            "metadata_completeness_state": self.metadata_completeness_state,
            "content_completeness_state": self.content_completeness_state,
            "safe_for_client_answering": self.safe_for_client_answering,
            # A2 additive trust surface.
            "trust_state": self.trust_state,
            "authorization_state": self.authorization_state,
            "sensitivity_known": self.sensitivity_known,
            "safe_for_live_read": self.safe_for_live_read,
            "safe_for_watcher_activation": self.safe_for_watcher_activation,
            "structure_ready": self.structure_ready,
            "structure_mapping_resolved": self.structure_mapping_resolved,
            "unresolved_quarantine_count": self.unresolved_quarantine_count,
            "trust_reason_codes": list(self.reason_codes),
        }


def _authorization_state(*, has_config: bool, enabled: bool) -> str:
    """Configured+enabled ⇒ authorized; configured+disabled ⇒ denied (operator turned it off);
    configless (index-only, no config entry) ⇒ unverified."""
    if not has_config:
        return AUTH_UNVERIFIED
    if not enabled:
        return AUTH_DENIED
    return AUTH_AUTHORIZED


def evaluate_root_trust(inp: RootTrustInputs) -> RootTrustDecision:
    """PURE trust decision. Reproduces the health projection's policy/index/completeness computation
    verbatim, then layers the A2 authorization + structure-readiness + trust-state gating on top."""
    counts = inp.counts
    state = inp.freshness_state
    folder_count = inp.folder_count
    file_count = inp.file_count
    gen_row = inp.gen_row
    current_fp = inp.current_fp

    # ---- policy verification (verbatim from health) ----
    policy_current = current_fp is None or (
        gen_row is not None and gen_row.get("policy_fingerprint") == current_fp
    )
    if current_fp is None:
        policy_verification = "unavailable"
    elif (
        gen_row is not None
        and gen_row.get("status") == "completed"
        and gen_row.get("policy_fingerprint") == current_fp
    ):
        policy_verification = "current"
    elif gen_row is None:
        policy_verification = "uncertified"
    else:
        policy_verification = "stale"
    policy_certified = policy_verification == "current"

    layers_metadata = file_count > 0
    layers_folder = folder_count > 0
    index_layers_ready = state in ("fresh", "degraded") and (layers_metadata or layers_folder)
    index_only_available = index_layers_ready

    # ---- completeness (verbatim from health) ----
    if gen_row is not None:
        reconciliation_done = gen_row.get("status") == "completed" and policy_current
        metadata_walk_done = reconciliation_done
    else:
        metadata_walk_done = inp.file_index_status == "bootstrapped"
        reconciliation_done = inp.file_index_status == "bootstrapped"
    if counts.get("metadata_indexed", 0) == 0:
        metadata_completeness_state = "none"
    elif metadata_walk_done:
        metadata_completeness_state = "complete"
    else:
        metadata_completeness_state = "partial"
    if counts.get("metadata_indexed", 0) == 0 or (
        counts.get("content_extracted", 0) == 0 and counts.get("content_searchable", 0) == 0
    ):
        content_completeness_state = "none"
    elif (
        counts.get("content_pending", 0) > 0
        or counts.get("failed", 0) > 0
        or not reconciliation_done
    ):
        content_completeness_state = "partial"
    else:
        content_completeness_state = "complete"

    from .source_indexer import derive_watcher_ready

    watcher_ready = derive_watcher_ready(
        gen_row=gen_row,
        current_fp=current_fp,
        folder_count=folder_count,
        legacy_ready=inp.legacy_watcher_ready,
    )

    safe_for_path_lookup_base = (
        policy_certified
        and state != "unknown"
        and (counts.get("metadata_searchable", 0) > 0 or folder_count > 0)
    )
    if not policy_certified:
        safe_for_content_answering = "none"
    elif content_completeness_state == "complete" and state in ("fresh", "degraded"):
        safe_for_content_answering = "complete"
    elif counts.get("content_searchable", 0) > 0 and state in ("fresh", "degraded"):
        safe_for_content_answering = "partial"
    else:
        safe_for_content_answering = "none"

    # ---- A2 authorization + trust-state gating ----
    authorization_state = _authorization_state(has_config=inp.has_config, enabled=inp.enabled)
    sensitivity_known = inp.has_config  # a configless root's sensitivity is unknown

    structure_mapping_resolved = inp.struct_mapping.structure_key is not None
    # OPERATIONAL structure readiness (A3 corrective clarification): mapping resolved AND backend up AND
    # ingestion (folder map) exists AND the structure run state is ready. Never mapping alone.
    structure_ready = bool(
        structure_mapping_resolved and inp.backend_available and folder_count > 0 and watcher_ready
    )

    reason_codes: list[str] = []
    if authorization_state == AUTH_DENIED:
        trust_state = TRUST_DENIED
        reason_codes.append(RC_ROOT_DISABLED)
    elif authorization_state == AUTH_UNVERIFIED:
        trust_state = TRUST_UNVERIFIED
        reason_codes.append(RC_AUTH_UNVERIFIED)
    else:
        trust_state = TRUST_SAFE
        if state == "unknown":
            trust_state = TRUST_BLOCKED
            reason_codes.append(RC_FRESHNESS_UNKNOWN)
        if not policy_certified:
            trust_state = TRUST_BLOCKED
            if policy_verification == "stale":
                reason_codes.append(RC_POLICY_STALE)
            elif policy_verification == "unavailable":
                reason_codes.append(RC_POLICY_UNAVAILABLE)
            else:
                reason_codes.append(RC_POLICY_UNCERTIFIED)
        if not index_layers_ready:
            trust_state = TRUST_BLOCKED
            reason_codes.append(RC_INDEX_LAYERS_UNREADY)
        if inp.unresolved_quarantine_count > 0:
            # A poison file reached the retry threshold and is quarantined: the metadata walk is
            # incomplete for this root, so it is NOT authoritative until an operator resolves it.
            trust_state = TRUST_BLOCKED
            reason_codes.append(RC_QUARANTINE_UNRESOLVED)

    is_safe = trust_state == TRUST_SAFE
    # Path lookup requires whole-root safety AND the health path-lookup base signal.
    safe_for_path_lookup = bool(is_safe and safe_for_path_lookup_base)
    # Live read is the strictest: safe root, enabled, authorized, and NOT sensitive.
    safe_for_live_read = bool(
        is_safe and inp.enabled and authorization_state == AUTH_AUTHORIZED and not inp.sensitive
    )
    if is_safe and inp.sensitive:
        reason_codes.append(RC_SENSITIVE_ROOT)
    if not inp.mapping_config_available:
        reason_codes.append(RC_STRUCTURE_MAPPING_UNAVAILABLE)
    elif not structure_ready:
        reason_codes.append(RC_STRUCTURE_DATA_UNREADY)

    return RootTrustDecision(
        root_key=inp.root_key,
        trust_state=trust_state,
        authorization_state=authorization_state,
        enabled=inp.enabled,
        sensitive=inp.sensitive,
        sensitivity_known=sensitivity_known,
        safe_for_path_lookup=safe_for_path_lookup,
        safe_for_live_read=safe_for_live_read,
        safe_for_content_answering=safe_for_content_answering,
        policy_verification=policy_verification,
        generation_status=(gen_row or {}).get("status") if gen_row else None,
        reconciliation_complete=bool(reconciliation_done),
        structure_mapping_resolved=structure_mapping_resolved,
        structure_mapping_reason=inp.struct_mapping.reason,
        structure_key=inp.struct_mapping.structure_key,
        structure_ready=structure_ready,
        index_only_available=index_only_available,
        freshness_status=state,
        metadata_completeness_state=metadata_completeness_state,
        content_completeness_state=content_completeness_state,
        watcher_ready=watcher_ready,
        unresolved_quarantine_count=int(inp.unresolved_quarantine_count),
        reason_codes=reason_codes,
    )


# ---- single-root gathering (serving / watcher) ----------------------------------------------------
def _mapping_inputs(
    app_config: Any, structure_roots_keys: list[str]
) -> tuple[bool, dict, list[str]]:
    """Return (mapping_config_available, structure_root_map, structure_namespace). Fail closed on a
    failed/invalid config load exactly like the health projection."""
    mapping_config_available = True
    if app_config is None:
        try:
            from hb_assistant.config.loader import load_config as _load_app_config

            app_config = _load_app_config()
        except Exception:
            mapping_config_available = False
            app_config = None
    if not mapping_config_available:
        return False, {}, []
    _app_ss = getattr(app_config, "source_structure", None)
    scan_roots = dict(getattr(_app_ss, "scan_roots", {}) or {})
    structure_root_map = dict(getattr(_app_ss, "structure_root_map", {}) or {})
    namespace = list(scan_roots.keys()) or list(structure_roots_keys)
    return True, structure_root_map, namespace


def gather_root_inputs(
    repo: Any,
    config: Any,
    app_config: Any,
    root_key: str,
    *,
    conn: Any = None,
) -> RootTrustInputs:
    """Gather the trust primitives for ONE root (serving/watcher path). Mirrors the health projection's
    per-root gathering; fail-closed on every optional read."""
    from hb_assistant.store.source_index_bootstrap_repository import (
        SourceIndexBootstrapRepository,
    )
    from hb_assistant.store.source_index_scan_generations_repository import (
        SourceIndexScanGenerationsRepository,
    )

    from .source_health_service import _freshness_state, _watchdog_available
    from .source_indexer import _root_fingerprint
    from .source_structure_repository import SourceStructureRepository

    norm_key = normalize_root_key(root_key)
    cfg_root = next(
        (r for r in getattr(config, "external_sources", []) if r.source_root_key == root_key),
        None,
    )
    has_config = cfg_root is not None
    enabled = bool(getattr(cfg_root, "enabled", True)) if has_config else True
    sensitive = bool(getattr(cfg_root, "sensitive", False)) if has_config else False
    current_fp = _root_fingerprint(cfg_root, config) if cfg_root is not None else None

    try:
        counts = repo.content_status_counts(root_key, conn=conn)
    except Exception:
        counts = {}
    try:
        file_count = int(repo.count_source_files(root_key, conn=conn))
    except Exception:
        file_count = 0

    srepo = SourceStructureRepository(str(repo.db_path))
    try:
        structure_roots = {r["root_key"]: r for r in srepo.list_roots(limit=100, conn=conn)}
    except Exception:
        structure_roots = {}
    mapping_config_available, structure_root_map, namespace = _mapping_inputs(
        app_config, list(structure_roots.keys())
    )
    if mapping_config_available:
        struct_mapping = resolve_structure_mapping(
            root_key, namespace, config_map=structure_root_map
        )
    else:
        struct_mapping = StructureRootMapping(norm_key, None, REASON_CONFIG_UNAVAILABLE)
    sroot = (
        structure_roots.get(struct_mapping.structure_key)
        if struct_mapping.structure_key is not None
        else None
    )
    folder_count = int((sroot or {}).get("folder_count") or 0)

    last_indexed = (sroot or {}).get("last_indexed_at")
    if last_indexed is None:
        try:
            from .source_connector_service import source_status

            last_indexed = (source_status(repo, config, conn=conn) or {}).get("last_indexed_at")
        except Exception:
            last_indexed = None
    freshness_state = _freshness_state(last_indexed_at=last_indexed, is_active=enabled)

    try:
        gen_row = (
            SourceIndexScanGenerationsRepository(str(repo.db_path)).latest_generations(conn=conn)
            or {}
        ).get(root_key)
    except Exception:
        gen_row = None
    try:
        bstate = (
            SourceIndexBootstrapRepository(str(repo.db_path)).get_bootstrap_state(root_key) or {}
        )
    except Exception:
        bstate = {}
    try:
        from hb_assistant.store.source_index_scan_quarantine_repository import (
            SourceIndexScanQuarantineRepository,
        )

        unresolved_quarantine = SourceIndexScanQuarantineRepository(
            str(repo.db_path)
        ).blocking_count(root_key, conn=conn)
    except Exception:
        # Fail CLOSED: if the quarantine count is unreadable, treat the root as blocked (non-zero) so an
        # unverifiable quarantine state never presents as safe.
        unresolved_quarantine = 1

    return RootTrustInputs(
        root_key=root_key,
        enabled=enabled,
        sensitive=sensitive,
        has_config=has_config,
        backend_available=_watchdog_available(),
        freshness_state=freshness_state,
        folder_count=folder_count,
        file_count=file_count,
        counts=dict(counts or {}),
        gen_row=gen_row,
        current_fp=current_fp,
        file_index_status=bstate.get("file_index_status"),
        legacy_watcher_ready=bool(bstate.get("watcher_ready")),
        struct_mapping=struct_mapping,
        mapping_config_available=mapping_config_available,
        unresolved_quarantine_count=int(unresolved_quarantine),
    )


def load_root_trust(
    repo: Any,
    config: Any,
    app_config: Any,
    root_key: str,
    *,
    conn: Any = None,
) -> RootTrustDecision:
    """The single-root serving/watcher authority: gather primitives then evaluate. Any unexpected error
    fails CLOSED to a blocked decision (never an exception that could surface as a raw gateway error)."""
    try:
        return evaluate_root_trust(
            gather_root_inputs(repo, config, app_config, root_key, conn=conn)
        )
    except Exception:
        return RootTrustDecision(
            root_key=normalize_root_key(root_key),
            trust_state=TRUST_BLOCKED,
            authorization_state=AUTH_UNVERIFIED,
            enabled=False,
            sensitive=True,
            sensitivity_known=False,
            safe_for_path_lookup=False,
            safe_for_live_read=False,
            safe_for_content_answering=CONTENT_NONE,
            policy_verification="unavailable",
            generation_status=None,
            reconciliation_complete=False,
            structure_mapping_resolved=False,
            structure_mapping_reason=REASON_CONFIG_UNAVAILABLE,
            structure_key=None,
            structure_ready=False,
            index_only_available=False,
            freshness_status="unknown",
            metadata_completeness_state="none",
            content_completeness_state="none",
            watcher_ready=False,
            unresolved_quarantine_count=1,
            reason_codes=[RC_INDEX_LAYERS_UNREADY],
        )


def root_readiness_envelope(decision: RootTrustDecision) -> dict[str, Any]:
    """The sanitized ``root_readiness`` block embedded in a fail-closed serving envelope."""
    return {
        "root_key": decision.root_key,
        "trust_state": decision.trust_state,
        "authorization_state": decision.authorization_state,
        "policy_verification": decision.policy_verification,
        "safe_for_path_lookup": decision.safe_for_path_lookup,
        "safe_for_live_read": decision.safe_for_live_read,
        "safe_for_content_answering": decision.safe_for_content_answering,
        "safe_for_watcher_activation": decision.safe_for_watcher_activation,
        "structure_ready": decision.structure_ready,
        "structure_mapping_resolved": decision.structure_mapping_resolved,
        "unresolved_quarantine_count": decision.unresolved_quarantine_count,
        "reason_codes": list(decision.reason_codes),
    }
