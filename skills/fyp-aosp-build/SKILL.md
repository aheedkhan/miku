---
name: fyp-aosp-build
description: FYP AOSP tree — android-16.0.0_r4, aosp_cf_x86_64_only_phone, vsoc_x86_64_only out dir, repo sync, lunch, build, cf.sh. Use for sync/build/boot work.
---

# FYP AOSP build

## Locked target
- Tag: `android-16.0.0_r4` (pinned — ground cannot move)
- Lunch: `aosp_cf_x86_64_only_phone` (name explicitly; not in COMMON_LUNCH_CHOICES alone)
- Out: `out/target/product/vsoc_x86_64_only/` — **not** `vsoc_x86_64`
- Device class: Cuttlefish, GMS-free, AVF on

## Rules
- Prefer AOSP on `/dev/nvme0n1` (unused 512 GB) once mounted — see AGENTS.md machine notes
- User runs privileged disk/`sudo` commands
- Cuttlefish: `cd /home/mania/Documents/FYP/cuttlefish && ./cf.sh start` only
- Do not quote CF results for GOV-023 Pixel-only claims

## Typical sequence (from PROGRESS)
1. Disk reclaim (`docker builder prune -af` — not image prune)
2. `repo init` + `repo sync` in tmux for `android-16.0.0_r4`
3. `lunch aosp_cf_x86_64_only_phone` → build
4. Boot **our** image; confirm `ro.build.user`
5. Only then: framework services / AppOps traces

## Cite
`PROGRESS.md`, `cuttlefish/README.md`, `10-roadmap.md`, `AGENTS.md` known-wrong row for out path.
