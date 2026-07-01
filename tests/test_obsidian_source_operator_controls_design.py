"""Phase 10I — operator control design is spec-only: lists FUTURE (Phase 10J) actions, executes none.

The review script exposes a pure-data design map and renders it into the safe report. This asserts the
design enumerates the four control domains + their future actions, and that the module exposes NO
executor for any of them (no apply/remove/merge/delete/rollback callable) — Phase 10I is read-only.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "obsidian_source_graph_review.py"
_spec = importlib.util.spec_from_file_location("graph_review_10i_design", _SCRIPT)
assert _spec and _spec.loader
gr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gr)


def test_design_lists_all_domains_and_future_actions():
    d = gr.OPERATOR_CONTROL_DESIGN
    assert set(d) == {"duplicate", "relationship", "identity", "rollback"}
    assert "mark_duplicate" in d["duplicate"] and "choose_canonical" in d["duplicate"]
    assert "accept_relationship" in d["relationship"] and "rollback_relationship" in d["relationship"]
    assert "request_reconcile" in d["identity"]
    assert "apply_rollback" in d["rollback"] and "preview_rollback" in d["rollback"]


def test_design_is_rendered_but_marked_not_executed_in_10i():
    md = gr._render_phase10i_report({"mode": "review"})
    assert "Operator Control Design" in md
    assert "executed_in_10i: false" in md
    assert "accept_relationship" in md and "mark_duplicate" in md


def test_module_exposes_no_executor_for_control_actions():
    # Phase 10I must not implement any of the future mutating actions — only report/inspect.
    action_names = {a for acts in gr.OPERATOR_CONTROL_DESIGN.values() for a in acts}
    for name in action_names:
        assert not hasattr(gr, name), f"unexpected executor for future action: {name}"
    # and no mutating verbs leaked into the module's public callables
    for verb in ("apply_", "merge_", "delete_", "rollback_", "write_link", "remove_link"):
        assert not any(callable(getattr(gr, n, None)) and n.startswith(verb) for n in dir(gr))
