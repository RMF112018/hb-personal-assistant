#!/usr/bin/env python3
"""Generate the non-authoritative Batch 1 capability-matrix Python module."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

EXPECTED_SHA256 = "6f758afd1f46c3ef4a5c06763faf21b2e4d8a2c01ed347a52b96a18f6db3c08e"
GENERATOR_ID = "scripts/generate_batch1_capability_registry.py:v1"


def render(payload: bytes) -> bytes:
    digest = hashlib.sha256(payload).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError(f"authorized matrix identity mismatch: {digest}")
    text = payload.decode("utf-8")
    if '"""' in text:
        raise ValueError("authorized matrix contains unsupported triple-quote sequence")
    header = (
        '"""GENERATED FILE — DO NOT EDIT.\n\n'
        f"Source SHA-256: {digest}\n"
        f"Generator: {GENERATOR_ID}\n"
        'Regenerate from the operator-authorized CSV; this module is not an independent authority.\n'
        '"""\n\n'
        f'MATRIX_SHA256 = "{digest}"\n'
        f'GENERATOR_ID = "{GENERATOR_ID}"\n'
        'MATRIX_CSV = """'
    )
    return (header + text + '"""\n').encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    generated = render(args.input.read_bytes())
    if args.check:
        actual = args.output.read_bytes() if args.output.exists() else b""
        if actual != generated:
            raise SystemExit("generated capability registry is stale")
        print(hashlib.sha256(actual).hexdigest())
        return 0
    args.output.write_bytes(generated)
    print(hashlib.sha256(generated).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
