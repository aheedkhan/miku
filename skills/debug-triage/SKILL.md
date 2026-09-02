---
name: debug-triage
description: >-
  Systematic debugging — reproduce, bisect, logs, strace/ltrace, gdb/lldb,
  logcat, journalctl, core dumps. Use when builds fail, crashes, hangs, wrong
  behavior, or "it worked yesterday."
---

# Debug triage

## Goal
Find the first wrong assumption fast; leave a short trail so future sessions don't rediscover it.

## Workflow (always)
1. **Reproduce** — minimal command, exact error, exit code
2. **Locate** — which layer? build | runtime | network | permission | data
3. **Instrument** — one tool at a time (log → strace → debugger)
4. **Hypothesis** — one sentence; test it; keep or discard
5. **Fix or document** — patch + note under `workspace/` or FYP `PROGRESS` if relevant

## Tool map
| Symptom | First tools |
|---------|-------------|
| Compile error | full command + first error only (ignore cascade) |
| Crash / SIGSEGV | `coredumpctl`, gdb/`lldb`, ASAN/UBSAN rebuild |
| Hang | `strace -f`, `perf top`, thread dumps |
| Android process | `adb logcat`, `dumpsys`, binder logs |
| Service / host | `journalctl -u`, `ss -lntp`, curl health |
| "Works on my machine" | env diff, container vs host, cwd, SELinux/`getenforce` |

## Rules
- Prefer **evidence** over vibes
- Don't restart the world before reading the error
- For FYP: never treat Cuttlefish results as Pixel GOV-023 proof
- Save the failing command + key log excerpt in the lab note

## Hand-offs
- Build system confusion → `lab-build` / `fyp-aosp-build`
- Writeup → `report-generation`
- Unknown malware crash → `malware-analysis` / `android-malware-analysis`
