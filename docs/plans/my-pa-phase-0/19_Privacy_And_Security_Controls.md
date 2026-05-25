# Privacy and Security Controls

Prepared: 2026-05-25

## Controls

| Data | Control |
| --- | --- |
| Tokens | Application Support auth cache; 700/600; never log/commit. |
| Certificate | ~/.secrets only; no PEM output. |
| Email bodies | Bounded retrieval; no full logs/default persistence. |
| Calendar bodies | Sanitized metadata; private-event conservatism. |
| Files | Cache outside repo; bounded parsed excerpts; no full logs. |
| SQLite | Application Support; no raw tokens. |
| Obsidian | User-visible source-linked output only. |
| Evidence | Sanitized local evidence only. |

## Required .gitignore

```gitignore
.local/
.hb-personal-assistant/
*.pem
*.pfx
*.key
*.crt
*.cer
*token*
*msal*
*.sqlite
*.sqlite3
*.db
cache/
logs/
docs/evidence/private/
```
