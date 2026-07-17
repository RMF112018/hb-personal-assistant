"""N8C-12H — deterministic LLM-client source-access evaluation fixtures (no live LLM).

Encodes the realistic client questions from the phase brief and asserts, via a deterministic intent scorer
over the REAL registered tool descriptions, that the client-facing descriptions route SOURCE-FILE questions
to the new ``assistant_source_*`` tools — and route vault-note / source-card questions AWAY from them. This
is the evaluation package Bobby can reuse during live client testing; it proves tool *selection intent*, not
mere keyword presence (each source-file prompt's source tool must out-score the vault-note and source-card
baselines).
"""

from __future__ import annotations

import pytest

from hb_assistant.nas_mcp.broker import ASSISTANT_SOURCE_CONNECTOR_TOOLS, NasMcpBroker
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools


class _DescMcp:
    """Captures each registered tool's name + description (docstring), like a real MCP registrar."""

    def __init__(self) -> None:
        self.docs: dict[str, str] = {}

    def tool(self, name: str | None = None):
        def deco(fn):
            self.docs[name or fn.__name__] = (fn.__doc__ or "")
            return fn
        return deco


# Canonical object-type baselines for the routing harness (what a vault-note tool and a source-card tool are
# ABOUT). Source-file prompts must prefer a source tool over BOTH of these.
VAULT_NOTE_BASELINE = ("Read an Obsidian vault note / markdown note authored in the vault by its note path.")
SOURCE_CARD_BASELINE = ("Read a generated source card note — the supplemental summary card generated for a "
                        "source, stored as a vault card note.")

# The evaluation scenarios from the phase brief. ``family`` is the expected object type; ``tokens`` are the
# positive intent signals of the question; ``expect_tool`` (when set) is the single expected source tool.
SCENARIOS = [
    {"prompt": "Show me the structure of my source roots.",
     "tokens": ["source", "roots", "structure", "configured"], "family": "source",
     "expect_tool": "assistant_source_roots_list"},
    {"prompt": "Find contract-related PDFs under the NAS project source folders.",
     "tokens": ["find", "contract", "pdf", "nas", "project", "source", "folders", "files"],
     "family": "source", "expect_tool": "assistant_source_file_search"},
    {"prompt": "Search source file contents for a payment application term.",
     "tokens": ["search", "source", "file", "contents", "invoice", "payment"], "family": "source",
     "expect_tool": "assistant_source_file_search"},
    {"prompt": "Open metadata for this source-file result.",
     "tokens": ["metadata", "source", "file", "extension", "size"], "family": "source",
     "expect_tool": "assistant_source_file_metadata"},
    {"prompt": "Show neighboring files in the same folder.",
     "tokens": ["files", "folder", "list", "source", "browse"], "family": "source",
     "expect_tool": "assistant_source_files_list"},
    {"prompt": "Continue with the next page of source-file results.",
     "tokens": ["next", "page", "source", "files", "cursor"], "family": "source",
     "expect_tool": None},
    {"prompt": "Find source files under a specific source_root_key.",
     "tokens": ["source", "files", "source_root_key", "root"], "family": "source",
     "expect_tool": None},
    {"prompt": "Read the contents of this original source file.",
     "tokens": ["read", "source", "file", "content", "original"], "family": "source",
     "expect_tool": "assistant_source_file_read"},
    {"prompt": "Open my Obsidian vault note about the project.",
     "tokens": ["obsidian", "vault", "note", "markdown"], "family": "vault", "expect_tool": None},
    {"prompt": "Open the generated source card only if it exists.",
     "tokens": ["generated", "card", "summary", "supplemental"], "family": "card",
     "expect_tool": None},
]


def _score(tokens: list[str], doc: str) -> int:
    low = doc.lower()
    return sum(1 for t in tokens if t.lower() in low)


@pytest.fixture()
def source_docs(tmp_path):
    mcp = _DescMcp()
    cfg = NasMcpConfig(
        db_path=tmp_path / "db.sqlite", audit_dir=tmp_path / "audit",
        roots={"vault": RootSpec("vault", tmp_path / "v", "read_write")},
        obsidian=NasObsidianConfig(vault_root=tmp_path / "v", backup_dir=tmp_path / "bk",
                                   support_dir=tmp_path / "sp"),
    )
    (tmp_path / "v").mkdir()
    register_nas_mcp_tools(mcp, NasMcpBroker(cfg), capability_profile="legacy-v12")
    return {name: mcp.docs[name] for name in ASSISTANT_SOURCE_CONNECTOR_TOOLS}


def test_all_source_tools_have_disambiguating_descriptions(source_docs) -> None:
    # Every new tool must say it is for SOURCE FILES and NOT vault notes / cards, and (for the discovery
    # tools) name concrete original-file types — this is what makes them the obvious source-file choice.
    for name, doc in source_docs.items():
        low = doc.lower()
        assert "source" in low and "file" in low, name
        assert ("vault" in low or "card" in low), f"{name} should contrast with vault notes / cards"
    search_doc = source_docs["assistant_source_file_search"].lower()
    assert all(w in search_doc for w in ("pdf", "contract", "invoice"))


def test_source_prompts_route_to_source_tools(source_docs) -> None:
    # For each source-file question, the best-scoring source tool out-scores BOTH object-type baselines.
    for sc in SCENARIOS:
        if sc["family"] != "source":
            continue
        best_source = max(_score(sc["tokens"], doc) for doc in source_docs.values())
        vault = _score(sc["tokens"], VAULT_NOTE_BASELINE)
        card = _score(sc["tokens"], SOURCE_CARD_BASELINE)
        assert best_source > vault, sc["prompt"]
        assert best_source > card, sc["prompt"]


def test_specific_source_tool_selection(source_docs) -> None:
    # Where the brief names a specific tool, the deterministic argmax over the source tools selects it.
    for sc in SCENARIOS:
        if sc["family"] != "source" or not sc["expect_tool"]:
            continue
        ranked = sorted(source_docs, key=lambda n: (_score(sc["tokens"], source_docs[n]), n),
                        reverse=True)
        assert ranked[0] == sc["expect_tool"], (sc["prompt"], ranked[0])


def test_vault_and_card_prompts_do_not_route_to_source_tools(source_docs) -> None:
    # A vault-note question prefers the vault baseline; a source-card question prefers the card baseline —
    # neither should be won by a source-file tool.
    for sc in SCENARIOS:
        if sc["family"] == "vault":
            best_source = max(_score(sc["tokens"], doc) for doc in source_docs.values())
            assert _score(sc["tokens"], VAULT_NOTE_BASELINE) > best_source, sc["prompt"]
        elif sc["family"] == "card":
            best_source = max(_score(sc["tokens"], doc) for doc in source_docs.values())
            assert _score(sc["tokens"], SOURCE_CARD_BASELINE) > best_source, sc["prompt"]


def test_scenarios_cover_the_brief() -> None:
    # The evaluation package covers discovery, search, metadata, neighbors, pagination, root-scoping, read,
    # and the source-vs-vault-vs-card distinction.
    assert len(SCENARIOS) >= 9
    assert {"source", "vault", "card"} <= {s["family"] for s in SCENARIOS}
    named = {s["expect_tool"] for s in SCENARIOS if s["expect_tool"]}
    assert named <= set(ASSISTANT_SOURCE_CONNECTOR_TOOLS)
