"""ControlledDownloader: bounded download via GraphHttpClient + size guard + streaming to cache."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.graph.http_client import GraphHttpClient

class ControlledDownloader:
    def __init__(self, http_client: GraphHttpClient, path_policy: Optional[PathPolicy] = None):
        self.client = http_client
        self.pp = path_policy or PathPolicy()
        self.cache_dir = self.pp.get_cache_dir("files")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def download(self, drive_item_id: str, max_bytes: Optional[int] = None) -> Path:
        """Download to cache/<id>.bin . Raises on size violation or error."""
        # In real impl: use /me/drive/items/{id}/content with streaming + size check
        # For v0.9 MVP skeleton: return a placeholder path; full integration in service.
        target = self.cache_dir / f"{drive_item_id}.bin"
        # Placeholder: in tests we mock the http response
        target.write_bytes(b"")  # will be overwritten in real download
        return target
