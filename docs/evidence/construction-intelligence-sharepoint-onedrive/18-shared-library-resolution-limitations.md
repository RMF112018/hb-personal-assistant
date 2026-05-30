# 18 — Shared-Library Resolution Limitations (OneDrive)

**Prompt:** Prompt 05 — OneDrive Discovery and Shared Library Posture
**Phase:** HB Construction Intelligence Phase 06 — SharePoint / OneDrive File Intelligence
**Date:** 2026-05-30
**Status:** Documented limitation. Resolution of shared libraries without identifiers is **not
forced** in this phase.

---

## 1. The limitation

A OneDrive **shared library** source (`onedrive_shared` / `onedrive_shared_library`) can only be
resolved to a canonical Graph `drive_id` when one of the following is already known:

- a pre-configured `drive_id` in the source registry, **or**
- a share URL (to encode + resolve via `/shares/{encoded}/driveItem`), **or**
- a remote-item lookup from another already-resolved drive item.

Microsoft Graph has **no** "list my shared libraries" delegated endpoint that returns stable
`drive_id`s without one of those inputs. `/me/drives` enumerates the caller's *own* drives, not
arbitrary shared libraries.

## 2. How this phase represents shared libraries

`graph files onedrive` (via `SiteDriveDiscovery.discover_onedrive`) returns a structured status —
**never a fabricated or forced resolution**:

| Condition | `status` | Behavior |
| --- | --- | --- |
| `drive_id` configured in registry | `pre_resolved` | Uses the configured id; no Graph call. |
| No `drive_id`, no share URL | `requires_share_url` | Reports the gap; **no** Graph call, **no** guess. |
| (registry posture) | `resolution_status: pending_source_resolution` carried through | Matches `sharepoint_onedrive_discovery_defaults.json` → `shared_library_without_drive_id: pending_source_resolution`. |

The seed source `od_shared_libraries_cloudtemp` (no `drive_id`, `resolution_status:
pending_source_resolution`) therefore reports `status: requires_share_url` with
`resolution_status: pending_source_resolution` (see `05-onedrive-discovery-proof.json`).

## 3. Personal vs business OneDrive

- **Business root** (`onedrive_business_root`): resolves via `/me/drive`; `/me/drives` enumeration
  populates `available_drives` and confirms `driveType`. → `resolved`.
- **Personal root** (`onedrive_personal_root`): may be **not provisioned** for the tenant account; a
  `404` on `/me/drive` maps to `status: unavailable` (no crash, no retry storm).

## 4. Explicit non-goals (this phase)

- Do **not** fabricate or guess a shared-library `drive_id`.
- Do **not** require, store, or encode a share URL (none is configured; doing so is deferred).
- Do **not** crawl shared-library contents.
- Do **not** change scopes or tighten permissions (deferred for the whole phase).

## 5. Future remediation (deferred)

When a share URL or remote-item reference is supplied for a shared library, a later prompt can add a
read-only `/shares/{encoded}/driveItem` resolution path to upgrade `requires_share_url` →
`pre_resolved`. Until then this is an honest, structured pending state.
