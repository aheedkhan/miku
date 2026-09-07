---
name: lab-iterate
description: >-
  Error→debug→fix loop until the lab requirement is met — including Win11
  Defender baseline then bypass when that is the explicit goal. Use for PE/.exe
  on WSL+Windows, RAT checkin, CVE harnesses, or any red→green research loop.
---

# Lab iterate (until done)

## Goal
Keep a tight loop until the **stated success criteria** pass — not until “it kinda works.”

```
define success → build → run test → FAIL?
   → capture error → debug → patch → rebuild → re-run SAME test
→ PASS → record evidence → (next phase if any)
```

## When to use
- WSL-built `.exe` won’t check in / crashes / blocked
- “Keep going until Defender doesn’t kill it” (**lab VM only**, explicit requirement)
- CVE harness flaky until A/B green
- Any multi-hour PE/implant bring-up

## Step 0 — Write success criteria (one card)
```markdown
## Success criteria
- [ ] Builds clean (mingw/MSVC command …)
- [ ] Checkin to C2 at <IP:port> within Ns
- [ ] Module X works (e.g. shell whoami)
- [ ] (If required) Default Defender real-time: no block / or documented bypass
- [ ] Detection twin written
- Snapshot / build / Defender cloud on/off noted
```
If Defender bypass is **not** in the list, do **not** start evasion — finish baseline first.

## The loop (every iteration)
1. **Build** — `lab-build` / `wsl-windows-exe` (Debug PE while developing)
2. **Run the same test command** — script it (`run_tests.py`, `make test`, one PowerShell line)
3. **On failure — classify**
   | Symptom | Action |
   |---------|--------|
   | Compile/link | First error only → `lab-build` |
   | Crash / AV exception | Windows debugger / Procmon → `debugger` + `wsl-windows-exe` |
   | No network / no checkin | `ss`/firewall/C2 bind/`C2_HOST` → fix config |
   | Defender quarantine / toast | Record Event ID; enter **Defender phases** below |
   | Wrong behavior | Log + conditional fix; don’t widen scope |
4. **Patch minimal** — one hypothesis per iteration
5. **Rebuild + re-run the identical test**
6. Tick criteria; `rag_remember` durable findings

Stop when **all** criteria boxes are checked (or user changes the goal).

## Defender phases (only if required)

### Phase A — Baseline (mandatory before bypass)
- Snapshotted Win11 lab VM, default Defender, note cloud on/off, HVCI, ASR
- Run **unsigned / current** lab PE with **no** evasion
- Capture: Defender Operational log, file path, SHA256, blocked or allowed
- Document honestly — many labs die here; that’s data

### Phase B — Bypass research (explicit criteria only)
One technique per iteration (examples — teach mechanisms, don’t spray):
- Packaging / signing / reputation path (lab cert)
- AMSI / ETW related experiments (separate builds)
- Loader vs static on-disk PE
- Living-off-the-land staging (still lab-only)

Each iteration:
1. Restore snapshot **or** use a fresh copy of the PE build
2. Apply **one** change
3. Re-run same launch + checkin test
4. Record: still blocked? Event IDs? which layer (cloud / RTP / ASR / Smart App Control)?
5. **Detection twin** for that technique (Sigma/YARA/ETW idea) — non-negotiable

### Phase C — Done
- Criteria green on the agreed Defender posture
- Notes + hashes in `workspace/malware-authoring/rat/projects/<name>.md`
- Analyst pass (`malware-analysis`) optional but preferred

## WSL-specific tips
- Develop/fix protocol under WSL + interop `.exe` for speed
- **Promote** to Win11 VM for any Defender claim
- C2 on WSL: `0.0.0.0` + guest-reachable IP in `config.h` — skill `wsl-windows-exe`

## Evidence template (paste each fail)
```markdown
### Iter N
- Test command:
- Result: FAIL — <compile|crash|network|defender>
- Evidence: (log excerpt / Event ID / bt)
- Hypothesis:
- Patch:
- Re-test: PASS/FAIL
```

## Hand-offs
| Need | Skill |
|------|-------|
| PE from WSL | `wsl-windows-exe` |
| RAT design | `windows-rat-dev` |
| WinDbg / stacks | `debugger` |
| Compile | `lab-build` |
| Formal writeup | `report-generation` |

## Never
- Claim Defender bypass on daily-driver without snapshot lab
- Change five evasion knobs in one iteration
- Skip baseline “because we know it’ll block”
- Optimize for third-party victims / “FUD packs”
- Mark done without re-running the success-criteria commands
