# 02 — Environment and Storage

## Mac baseline

| Item | Value |
|---|---|
| Host | `MacBook-Pro.local` |
| Kernel | Darwin 25.6.0 arm64 |
| macOS | 26.6 (Build 25G5028f) |
| Python | 3.14.5 |
| SQLite | 3.53.1 |
| RAM | 24 GiB (`hw.memsize=25769803776`) |
| Scratch volume | `/tmp` on `/System/Volumes/Data` — 143 GiB free |

## NAS (TheLakeHouseNAS)

| Item | Value |
|---|---|
| Hostname | `TheLakeHouseNAS` |
| Kernel | Linux 4.4.302+ x86_64 (Synology DS923+, `synology_r1000_923+`) |
| RAM | 19 GiB total, ~15 GiB available |
| Swap | 13 GiB |
| Python | 3.x with `sqlite3` **3.40.0** |
| Uptime | ~18h, load ~0.06 |

### Disk

| Path | Size | Used | Avail | FS |
|---|---|---|---|---|
| `/volume1` | 16T | 3.6T | 13T | btrfs (SSD, `cachedev_0`) |
| `/volume1/personal-assistant/app-support/tmp` | 16T | 3.6T | 13T | btrfs subvol |

### Mounts (relevant)

- `/volume1` → btrfs on `/dev/mapper/cachedev_0` (rw, ssd, synoacl)
- `/volume1/personal-assistant` → btrfs subvol `@syno/personal-assistant`

### Listeners (boundary check)

```
8000/9000/9443 not listening
```

Tailscale serve/funnel: no active output.

## Storage implication

NAS benchmark copy lives on **local btrfs `/volume1`** — the same storage class as the N3 final DB path. This satisfies the architectural question (backend + DB co-located on NAS) without using SMB/NFS mount from Mac.
