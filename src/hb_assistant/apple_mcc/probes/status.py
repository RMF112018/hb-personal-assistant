"""Probe status vocabulary (fail-closed)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ProbeState(str, Enum):
    OK = "ok"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    DENIED = "denied"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass(frozen=True)
class ProbeResult:
    domain: str
    state: ProbeState
    detail: str = ""
    selected: str | None = None
    candidates: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        d["candidates"] = list(self.candidates)
        return d

    @property
    def ok(self) -> bool:
        return self.state is ProbeState.OK
