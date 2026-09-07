---
name: debug-triage
description: >-
  Systematic debugging — reproduce, classify compile vs runtime, logs, strace,
  then debugger. Use for build failures, crashes, hangs, wrong behavior.
---

# Debug triage

## Goal
Find the **first wrong assumption** fast. Leave a trail so the next session doesn't rediscover it.

## Pipeline
```
reproduce → classify layer → cheap instruments → debugger if needed → fix → re-test
```

1. **Reproduce** — exact command, cwd, env, exit code, full error text
2. **Classify**
   - **build** → `lab-build` (first compiler error only)
   - **test fail** → read assertion; keep test red until fixed (`test-harness`)
   - **crash / SIGSEGV / access violation** → ASAN rebuild or `debugger`
   - **hang** → `strace -f` / thread dump / `debugger` + `thread apply all bt`
   - **wrong result** — bisect input; conditional breakpoints
3. **One instrument at a time** — log → strace → debugger (don't stack everything)
4. **Hypothesis** — one sentence; test; keep or discard
5. **Fix + re-run the same repro/test**
6. **Note** under `workspace/` (command + excerpt + root cause)

## Tool map
| Symptom | First tools |
|---------|-------------|
| Compile error | full cmd + **first** error; `make VERBOSE=1` |
| Link error | undefined ref → which `.o`/`-l` missing |
| Crash Linux | ASAN build **or** `gdb`/`lldb` + `bt full` (skill `debugger`) |
| Crash Windows | WinDbg/`!analyze -v` on lab VM |
| Hang | `strace -f`, `perf top`, `thread apply all bt` |
| Android Java | `adb logcat`, jdb / Studio |
| Android native | tombstone + lldb (skill `debugger`) |
| Service/host | `journalctl -u`, `ss -lntp` |
| Env drift | container vs host, `cwd`, `getenforce` |

## Evidence over vibes
- Paste the failing command and the first error block into notes
- Don't "restart the world" before reading the error
- After fix: same test must go green (or mark `[UNVERIFIED]`)

## Hand-offs
| Need | Skill |
|------|-------|
| Compile flags / mingw / cmake | `lab-build` |
| Breakpoints / cores / WinDbg | `debugger` |
| New failing check | `test-harness` |
| Malware sample crash | `malware-analysis` (isolated VM) |
| Writeup | `report-generation` |
