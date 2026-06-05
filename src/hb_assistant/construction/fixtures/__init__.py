"""Canonical fixture inventory for the construction-agent.

Five fixture kinds — one module each:

- ``graph_delta``       synthetic Microsoft Graph /delta response pages
- ``source_registry``   alternate Source Registry payloads
- ``review_policy``     inventory rows exercising every seeded rule
- ``model_output``      valid + invalid raw classification outputs
- ``procore``           alternate Procore endpoint + projects payloads

Use the :func:`iter_fixtures` helper or :data:`ALL_FIXTURES` to walk the
full inventory programmatically. The :class:`FixtureHarness` validates
every fixture against its target schema or service.
"""

from __future__ import annotations

from typing import Any, Iterator

from .graph_delta import GRAPH_DELTA_FIXTURES
from .harness import FixtureHarness, HarnessReport
from .model_output import INVALID_FIXTURES, VALID_FIXTURES
from .procore import PROCORE_CONTRACT_FIXTURES, PROCORE_PROJECTS_FIXTURES
from .review_policy import REVIEW_POLICY_FIXTURES
from .source_registry import SOURCE_REGISTRY_FIXTURES

ALL_FIXTURES: dict[str, dict[str, Any]] = {}

for _name, _payload in GRAPH_DELTA_FIXTURES.items():
    ALL_FIXTURES[f"graph_delta:{_name}"] = {"kind": "graph_delta", "payload": _payload}

for _name, _payload in SOURCE_REGISTRY_FIXTURES.items():
    ALL_FIXTURES[f"source_registry:{_name}"] = {"kind": "source_registry", "payload": _payload}

for _name, _payload in REVIEW_POLICY_FIXTURES.items():
    ALL_FIXTURES[f"review_policy:{_name}"] = {"kind": "review_policy", "payload": _payload}

for _name, _payload in VALID_FIXTURES.items():
    ALL_FIXTURES[f"model_output_valid:{_name}"] = {
        "kind": "model_output_valid",
        "payload": _payload,
    }

for _name, _payload in INVALID_FIXTURES.items():
    ALL_FIXTURES[f"model_output_invalid:{_name}"] = {
        "kind": "model_output_invalid",
        "payload": _payload,
    }

for _name, _payload in PROCORE_CONTRACT_FIXTURES.items():
    ALL_FIXTURES[f"procore_contract:{_name}"] = {"kind": "procore_contract", "payload": _payload}

for _name, _payload in PROCORE_PROJECTS_FIXTURES.items():
    ALL_FIXTURES[f"procore_projects:{_name}"] = {"kind": "procore_projects", "payload": _payload}


KIND_ALIASES = {
    "graph_delta": ("graph_delta",),
    "source_registry": ("source_registry",),
    "review_policy": ("review_policy",),
    "model_output": ("model_output_valid", "model_output_invalid"),
    "procore": ("procore_contract", "procore_projects"),
}


def iter_fixtures(kind: str | None = None) -> Iterator[tuple[str, dict[str, Any]]]:
    """Iterate (name, entry) pairs across the inventory, optionally filtered by kind alias."""

    if kind is None:
        yield from ALL_FIXTURES.items()
        return
    if kind not in KIND_ALIASES:
        raise KeyError(f"unknown fixture kind {kind!r}; allowed: {sorted(KIND_ALIASES)}")
    allowed = set(KIND_ALIASES[kind])
    for name, entry in ALL_FIXTURES.items():
        if entry["kind"] in allowed:
            yield name, entry


__all__ = [
    "ALL_FIXTURES",
    "FixtureHarness",
    "GRAPH_DELTA_FIXTURES",
    "HarnessReport",
    "INVALID_FIXTURES",
    "KIND_ALIASES",
    "PROCORE_CONTRACT_FIXTURES",
    "PROCORE_PROJECTS_FIXTURES",
    "REVIEW_POLICY_FIXTURES",
    "SOURCE_REGISTRY_FIXTURES",
    "VALID_FIXTURES",
    "iter_fixtures",
]
