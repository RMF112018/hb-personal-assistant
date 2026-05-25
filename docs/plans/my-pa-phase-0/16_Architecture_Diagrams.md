# Architecture Diagrams

## System

```text
Microsoft 365 → Graph Read Layer → Normalizers → SQLite Source Registry
                                        ↓
                              File Cache / Parsers
                                        ↓
                           Local Models / Extraction
                                        ↓
                         Obsidian Marker-Bounded Output
```

## Auth

```text
MSAL delegated login → token cache → TokenClassifier
  ├─ scp present → runtime allowed
  └─ roles-only → mail/calendar runtime denied
```

## Morning Run

```text
launchd/manual → catch-up gate → sync → parse → extract → retrieve context → brief → Obsidian → evidence
```

## Source Links

```text
source_records ↔ source_links ↔ action_items/parser_outputs/brief_sections
```
