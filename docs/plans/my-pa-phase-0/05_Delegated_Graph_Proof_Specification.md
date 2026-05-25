# Delegated Graph Proof Specification

Prepared: 2026-05-25

## Gate

No production retrieval workflow is accepted until delegated Graph proof is complete.

## Required Proofs

| Step | Target | Action | Evidence |
| --- | --- | --- | --- |
| 1 | /me | GET /me safe select | Bobby user context proof. |
| 2 | Mail metadata | List bounded messages with select/top | Sanitized metadata. |
| 3 | Message body | Retrieve one safe body | Redacted body-access proof. |
| 4 | Body mention | Live safe sample or fixture plus live body proof | Body-only Bobby mention included. |
| 5 | calendarView | Retrieve default calendar window | Sanitized event metadata. |
| 6 | Attachment metadata | List metadata from message/event sample | Metadata or no-sample evidence. |
| 7 | File metadata | Resolve one driveItem | Metadata proof. |
| 8 | Controlled download | Download one small approved eligible file | Hash/size/cache path only. |
| 9 | App-only rejection | Use fixture/app-only classifier | Mail/calendar runtime fails closed. |
| 10 | Sensitive scan | Scan repo and outputs | No tokens/private keys/cache/SQLite committed. |

## Safe Request Patterns

```http
GET https://graph.microsoft.com/v1.0/me?$select=id,displayName,userPrincipalName,mail
GET https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$select=id,conversationId,internetMessageId,subject,from,toRecipients,ccRecipients,receivedDateTime,bodyPreview,hasAttachments,webLink&$top=25
GET https://graph.microsoft.com/v1.0/me/messages/{message-id}?$select=id,conversationId,subject,from,toRecipients,ccRecipients,receivedDateTime,body,bodyPreview,webLink
GET https://graph.microsoft.com/v1.0/me/calendarView?startDateTime={start}&endDateTime={end}
GET https://graph.microsoft.com/v1.0/me/messages/{message-id}/attachments?$select=id,name,contentType,size,isInline,lastModifiedDateTime
GET https://graph.microsoft.com/v1.0/me/drive/items/{item-id}?$select=id,name,size,file,folder,webUrl,parentReference,lastModifiedDateTime,eTag,cTag
```

## Evidence Redaction

Allowed: endpoint path, HTTP status, token class, tenant, user UPN/mail, scope names, hashed/truncated IDs, file size/MIME/hash.  
Forbidden: access/refresh tokens, private keys, PEM, full bodies, full file text, raw sensitive content.

## Acceptance

Delegated token contains `scp`, identifies Bobby, uses tenant `0e834bd7-628b-42c8-b9ec-ecebc9719be4`, and proves `/me`, mail, body, calendarView, attachment, file metadata, and controlled download or policy-blocked download.
