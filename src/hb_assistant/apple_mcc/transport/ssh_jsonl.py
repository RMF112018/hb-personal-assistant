"""SSH JSONL transport (local-file dry path for tests)."""

from __future__ import annotations

from pathlib import Path

from hb_assistant.apple_mcc.contracts.batch_envelope import BatchEnvelope


def write_jsonl(path: Path, envelopes: list[BatchEnvelope]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for env in envelopes:
            env.validate()
            f.write(env.to_json_line() + "\n")


def read_jsonl(path: Path) -> list[str]:
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
