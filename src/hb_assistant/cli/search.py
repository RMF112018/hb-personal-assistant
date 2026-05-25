"""CLI for retrieval / search (Phase 11).

`hb-assistant search "query" --json` : deterministic + (if available) semantic retrieval over redacted excerpts/previews.
Safe, bounded, source-linked results only. No full content.
"""

from __future__ import annotations

import json

import typer

from hb_assistant.retrieval import Retriever
from hb_assistant.store.repositories import Store

app = typer.Typer(help="Retrieval & search (deterministic + gated semantic over redacted excerpts). Dry-run safe.")


@app.command("search")
def search_cmd(
    query: str = typer.Argument(..., help="Search query (keywords or natural language)"),
    limit: int = typer.Option(5, "--limit", min=1, max=20),
    semantic: bool = typer.Option(True, "--semantic/--no-semantic", help="Enable semantic ranking (requires Ollama embeddings or falls back)"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Search redacted content (parser excerpts, email previews, etc). Returns hits + provenance links."""
    store = Store()
    retr = Retriever(store=store)
    hits = retr.search(query, limit=limit, use_semantic=semantic)

    results = []
    for h in hits:
        results.append({
            "source_record_id": h.source_record_id,
            "type": h.content_type,
            "excerpt": h.text_excerpt[:400] + ("..." if len(h.text_excerpt) > 400 else ""),
            "score": h.score,
            "links": h.links or [],
            "meta": h.metadata,
        })

    payload = {
        "command": "search",
        "query": query,
        "limit": limit,
        "semantic": semantic,
        "hits": results,
        "note": "Redacted excerpts + source links only. Deterministic keyword + cosine (Ollama if available). No full content. Use for workstream context assembly.",
    }
    if json_out:
        typer.echo(json.dumps(payload, indent=2, default=str))
    else:
        typer.echo(f"search: {len(results)} hits for '{query}'")
        for r in results:
            typer.echo(f"  [{r['score']}] {r['type']} (src={r['source_record_id']}): {r['excerpt'][:80]}...")
    raise typer.Exit(0)
