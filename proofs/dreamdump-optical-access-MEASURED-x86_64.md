# dreamdump 0.6.0 — optical access as a plain user, no capability (MEASURED, x86_64)

**Date:** 2026-10-12 · **Where:** test VM `test-fedora` (Fedora 44, kernel 7.1.3; SELinux active —
context `unconfined_u:unconfined_r:unconfined_t` — mode not recorded),
USB-passthrough Plextor PX-760A (fw 1.07) as `/dev/sr1`, an audio CD inserted.
**Binary:** upstream release asset `dreamdump-_linux_amd64` 0.6.0 (sha256 `45ccf5152536ce2e…`),
`vcs.revision` = tag commit `3a17404`, **no file capability** (`getcap` empty).
**User:** `gmipf`, groups `gmipf wheel` — **not** in `cdrom` or `disk`. Device ACL from systemd's
uaccess (`user:gmipf:rw-`, autologin seat).

No ledger row: this package ships **no** mechanism of ours (no `%caps`, no udev rule, no setcap,
no permissions profile), so `proof-status.sh` has nothing to cover. Optical node access is systemd's
own `70-uaccess.rules`. This note records why the package can ship without `cap_sys_rawio`.

## Kernel view (`strace -e openat,ioctl`)

| phase | `openat("/dev/sr1", O_RDWR…)` | SG_IO by opcode → ioctl ret / SCSI status |
|---|---|---|
| GREEN, ACL present | `= 7` | `0x12` INQUIRY ×1 → 0/GOOD · `0xBE` READ CD ×2 → 0/GOOD |
| GREEN, MPF's own args (`--speed=24 --retries=20`) | ok | `0x12` → 0/GOOD · **`0xBB` SET CD SPEED → 0/GOOD** · `0xBE` → 0/GOOD |
| RED, `setfacl -x u:gmipf /dev/sr1` | **`= -1 EACCES`** | none sent |
| GREEN again, ACL restored by `udevadm trigger --action=change` | ok | reads again |

No opcode ≥ 0xC0 in any phase. Log of the green run: drive identified
(`Drive: PLEXTOR - DVDR PX-760A …`), `Set Read Speed to:4224 kbs`, sectors read from 44990 on.

## Whole source, not just the paths that ran

The run covers only what executed in ~45 s on a drive dreamdump does not list. At tag 0.6.0 the
entire code base sets a SCSI opcode in exactly three places (`OperationCode:` in
`scsi/scsi_commands/*.go`): `COMMON_INQUIRY = 0x12`, `MMC_READ_CD = 0xBE`,
`MMC_SET_CD_SPEED = 0xBB`. No other assignment form, no hand-built CDB, a single `SG_IO` call
site (`scsi/driver/sgio/sg.go`). All three are on the kernel's unprivileged list
(`scsi_cmd_allowed`; 0xBB because the node is opened read-write). So no drive-specific path can
need the capability either.

`fedora/dreamdump/dreamdump-build.sh` re-checks this on every build and fails on any new
opcode, so an automatic version bump cannot silently break access for users.

## Found on the way (upstream, not ours)

- **A failed drive open exits 0.** `exit_codes` starts with `UNKNOWN_DRIVE = iota` (= 0), and
  both failure paths in `drive/setup/mod.go` (bad name, open failed) use it. The RED phase above
  printed `Drive couldn't be found or disc is incorrect` and exited **0**. The manpage says so.
- **The 0.6.0 binary reports `build: 0.6.0-rc2`**: `VERSION` in `main.go` was not bumped for the
  tag (main has since moved to 0.6.1).
- **Drives not in the built-in list run with defaults, without a warning** (DATA_SUB_C2,
  offset 0, 40 sectors per command). The Plextor is not listed; it read, very slowly.

Not measured: aarch64 (build-tested only), a real GD-ROM, a listed drive.
