"""DriveItemClient + attachment metadata (metadata-first, controlled download later)."""

from __future__ import annotations

from typing import List, Optional

from hb_assistant.normalize.attachment import Attachment
from hb_assistant.normalize.drive_item import DriveItem

from .http_client import GraphHttpClient


class DriveItemClient:
    def __init__(self, http_client: GraphHttpClient):
        self.client = http_client

    def get_item(self, item_id: str) -> Optional[DriveItem]:
        url = f"/me/drive/items/{item_id}?$select=id,name,size,file,folder,webUrl,parentReference,lastModifiedDateTime,eTag,cTag"
        data = self.client.get(url)
        return DriveItem(
            id=data.get("id"),
            name=data.get("name"),
            size=data.get("size"),
            web_url=data.get("webUrl"),
            is_file=bool(data.get("file")),
            is_folder=bool(data.get("folder")),
            parent_reference=data.get("parentReference"),
            last_modified=data.get("lastModifiedDateTime"),
            e_tag=data.get("eTag"),
            c_tag=data.get("cTag"),
        )

    def list_children(self, parent_id: str = "root", top: int = 10) -> List[DriveItem]:
        url = f"/me/drive/items/{parent_id}/children?$top={top}&$select=id,name,size,file,folder,webUrl,lastModifiedDateTime"
        data = self.client.get(url)
        items = []
        for it in data.get("value", []):
            items.append(DriveItem(
                id=it.get("id"),
                name=it.get("name"),
                size=it.get("size"),
                is_file=bool(it.get("file")),
                is_folder=bool(it.get("folder")),
            ))
        return items

    # Attachment metadata (example; full would be per message/event)
    def list_attachments(self, parent_message_id: str) -> List[Attachment]:
        url = f"/me/messages/{parent_message_id}/attachments?$select=id,name,contentType,size,isInline,lastModifiedDateTime"
        data = self.client.get(url)
        atts = []
        for a in data.get("value", []):
            atts.append(Attachment(
                id=a.get("id"),
                parent_source_record_id=0,  # caller resolves
                name=a.get("name"),
                content_type=a.get("contentType"),
                size=a.get("size"),
                is_inline=a.get("isInline", False),
            ))
        return atts
