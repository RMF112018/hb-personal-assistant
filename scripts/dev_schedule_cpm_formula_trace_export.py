#!/usr/bin/env python3
"""Export CPM formula trace evidence from a copied schedule database (read-only)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hb_assistant.config.db_path_guard import assert_not_live_db
from hb_assistant.construction.analytics.schedule_cpm_formula_trace import (
    CpmChainResolutionError,
    ScheduleCpmFormulaTraceExporter,
)
from hb_assistant.construction.schedule_clean_db.guards import (
    assert_clean_copy_path,
    require_confirm_clean_copy,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--schedule-version-key", required=True)
    parser.add_argument("--out-dir", required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--latest", action="store_true")
    group.add_argument("--cpm-run-id")
    parser.add_argument("--allow-partial-chain", action="store_true")
    parser.add_argument("--allow-mismatches", action="store_true")
    parser.add_argument("--tolerance", type=float, default=0.0)
    parser.add_argument("--confirm-clean-copy", action="store_true")
    parser.add_argument("--allow-custom-copy-path", action="store_true")
    parser.add_argument("--technical", action="store_true")
    args = parser.parse_args(argv)

    try:
        assert_not_live_db(args.db_path, context="cpm formula trace export")
        if not args.allow_custom_copy_path:
            require_confirm_clean_copy(args.confirm_clean_copy)
            assert_clean_copy_path(
                args.db_path,
                allow_custom_copy_path=args.allow_custom_copy_path,
            )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    exporter = ScheduleCpmFormulaTraceExporter(db_path=args.db_path)
    try:
        _package, exit_code = exporter.export(
            schedule_version_key=args.schedule_version_key,
            out_dir=args.out_dir,
            latest=args.latest,
            cpm_run_id=args.cpm_run_id,
            allow_partial_chain=args.allow_partial_chain,
            tolerance=args.tolerance,
            technical=args.technical,
        )
    except CpmChainResolutionError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 4
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 4

    if exit_code and args.allow_mismatches:
        return 0
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
