"""ControlledDownloader: bounded streaming download via Graph + size guard + hash prep to cache."""

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
        """Stream download of /me/drive/items/{id}/content to cache/<id>.bin .

        Uses GraphHttpClient retry + streaming (no full body in mem). Enforces max_bytes.
        Returns the target path on success. Raises ValueError/GraphHttpError on violation or failure.
        """
        target = self.cache_dir / f"{drive_item_id}.bin"
        url_path = f"/me/drive/items/{drive_item_id}/content"
        # delegated scopes sufficient for Drive.Read
        self.client.download_to_file(
            url_path,
            target,
            max_bytes=max_bytes,
            scopes=["https://graph.microsoft.com/Files.Read"],
        )
        return target
