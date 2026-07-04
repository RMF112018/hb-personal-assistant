# 03 — Current Path Inventory (redacted)

Placeholders: `<mac-obsidian-vault>` = Mac vault; `<mac-synologydrive-work-root>` = SynologyDrive Work mirror;
`<mac-onedrive-*>` = OneDrive CloudStorage roots; `<nas-vault-root>` / `<nas-source-root>` = proposed NAS targets.
Full absolute paths withheld (see local-sensitive / config truth).

## Mac (source)
| Item | Value |
|---|---|
| `<mac-obsidian-vault>` | **4.9 MB, ~155 live `.md`**; top dirs incl. `Source Notes/`, `Email Archive/`, `Daily/`, `Work/`, `Home/`, `Attachments/` |
| CloudStorage roots (exist, 0700, on-demand — **not enumerated**) | `SynologyDrive-BFmacSync`, `OneDrive-HedrickBrothersConstruction`, `OneDrive-Personal`, `OneDrive-SharedLibraries-OneDriveCloudTemp` |
| app-support (N3/N4A) | `/volume1/personal-assistant/app-support` (already on NAS) |

## Source-root populations (DB `source_intelligence_sources`, 9,128 rows)
| `source_root_key` | sources | migration class |
|---|---|---|
| `__vault_notes__` | 5,002 | vault filesystem (mirror) |
| `hb-onedrive` | 3,470 | OneDrive/Graph (re-provision, not FS) |
| `docs-test` | 526 | scratch (ignore) |
| `syn-work` | 126 | SynologyDrive FS (repoint/copy — operator decision) |
| `manual-test` | 2 | scratch (ignore) |
| `syn-work-email-attachments` | 2 | SynologyDrive FS |

Generated vault notes: 195 (`source_intelligence_generated_notes`), vault-relative under `Source Notes/…`.

## NAS (target — current state, metadata only)
| Path | State |
|---|---|
| `/volume1/personal-assistant/vault` | **absent** |
| `/volume1/personal-assistant/source-roots` | exists, **empty** (777 bfetting) |
| `/volume1` user shares | `ActiveBackupforBusiness, Music, P6Datat, docker, gituser, homes, personal-assistant, web, web_packages` |
| `syn-work` NAS-native path (operator-confirmed) | **`/volume1/homes/bfetting/Work`** — EXISTS (bfetting:users 777); top-level includes `NAS - HB` + `Altman` |

⇒ The `syn-work` NAS-native path is **CONFIRMED** (operator-provided; verified read-only). Its top-level segments
(`NAS - HB`, `Altman`) exactly match the two top-level segments of the 126 `syn-work` rel_paths (101 + 25) → identical
rel_path tree. Traverse chain `/volume1/homes`(777) → `/volume1/homes/bfetting`(755) → `Work`(777) — all others-x, `Work`
others-readable → **`personal-assistant-svc` can read it read-only** without ACL/bind/copy. ⇒ same-key repoint viable (see 04/05).
