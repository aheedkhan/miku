---
name: fyp-enforcement
description: FYP enforcement layer — twelve mediators, PolicyEngine verdicts, AppOps/PermissionChecker camera-mic risk ENF-050/051. Use when designing or tracing hooks.
---

# FYP enforcement layer

## Model
Each surface (Camera, Mic, Clipboard, Storage, USB, BT, NFC, Screenshot, ShareIntent, Location, Network, Install) asks **PolicyEngine**, applies one of four verdicts, logs to **SecurityLog**.

## Critical uncertainty — camera/mic
**REFUTED:** hooking `AppOpsService.startOperation()` (`ENF-050`/`051`).

**Current understanding:** `PermissionChecker → startProxyOpNoThrow → startProxyOperationWithState`, with `checkOp` for camera/mic often served from **in-process cache** (`sAppOpModeCache`) — **no binder trip**, so a binder-level hook may see nothing.

## After AOSP tree exists — priority trace
1. Debug-log / breakpoint every `IAppOpsService` entry (and PermissionChecker paths)
2. Open camera on Cuttlefish build
3. Record which methods fire (file:line)
4. Decide: viable hook site, or redesign enforcement for camera/mic (may need different choke point)
5. Update verification ledger / raise CR against `14` if the locked requirement wording must change — do not silently edit descriptive docs

## Until traced
Treat headline camera DENY demo as **`[UNVERIFIED]` / at risk**. Do not promise the demo.

## Related docs
`03`, `03a`, `16`, `AGENTS.md` known-wrong table, `requirements.json` query for camera.
