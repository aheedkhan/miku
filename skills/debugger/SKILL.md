---
name: debugger
description: >-
  Use debuggers effectively — gdb, lldb, WinDbg/cdb, Android lldb/jdwp, cores,
  breakpoints, backtraces, watchpoints. Use when a crash needs a stack, a hang
  needs threads, or "step through this path" on a lab binary.
---

# Debugger playbook

## Goal
Turn a crash/hang/wrong-path into **evidence**: backtrace, registers, locals, watch hit — then a one-line root cause.

## Pick a debugger
| Target | Debugger | Notes |
|--------|----------|-------|
| Linux userland | **gdb** (or **lldb**) | Default for C/C++/Rust labs on Linux/WSL |
| macOS | **lldb** | |
| Windows userland | **WinDbg** / **cdb** / VS debugger | Lab VM or Windows host — **not** gdb on a PE from WSL |
| PE built in WSL | Build with mingw → run `.exe` via interop / VM → debug on **Windows** | Skill `wsl-windows-exe` |
| Android native | **lldb** via `adb jdwp` / ndk-gdb | Device/emulator + unstripped `.so` when possible |
| Android Java | **jdb** / Android Studio debugger | Attach to app PID |
| Python | `python -m pdb` / `breakpoint()` | |
| Core dump only | gdb `core-file` / `lldb -c` | Enable cores first |

## Golden rules
1. **Reproduce outside the debugger once** — know the exact command + exit code
2. Build **Debug** (`-g` / `CMAKE_BUILD_TYPE=Debug` / `cargo build`) — strip kills stacks
3. For memory bugs prefer **ASAN/UBSAN** rebuild before deep stepping
4. One hypothesis per session stretch — don't spray breakpoints blindly
5. Record: command, break location, `bt`, relevant locals, conclusion

## gdb (Linux / WSL) — essentials
```bash
# run with args
gdb -q --args ./labrat --port 8080
(gdb) set pagination off
(gdb) break main
(gdb) run
(gdb) bt              # backtrace
(gdb) bt full         # locals on stack
(gdb) info registers
(gdb) frame 2
(gdb) p/x $rax
(gdb) list
(gdb) next / step     # over / into
(gdb) finish
(gdb) watch ptr       # write watchpoint
(gdb) catch throw     # C++ exceptions
(gdb) thread apply all bt
(gdb) generate-core-file
```

Core after crash:
```bash
ulimit -c unlimited
./program …   # crashes → core
gdb ./program core
(gdb) bt full
```

With ASAN binary: still use gdb for stack; ASAN report often enough alone.

## lldb
```bash
lldb ./program -- arg1 arg2
(lldb) b main
(lldb) run
(lldb) bt
(lldb) frame variable
(lldb) thread backtrace all
```

## WinDbg / cdb (Windows lab VM or host — for .exe)

PE binaries from WSL mingw are still **Windows** processes. Debug them with WinDbg/cdb/VS
on Windows (or the lab VM), not `gdb` inside WSL.

```text
.sympath srv*C:\symbols*https://msdl.microsoft.com/download/symbols
.reload
bp module!Function
g
k          # stack
dv         # locals
!analyze -v
```

From WSL after a crash on interop: note the Windows PID / Event Log, then attach cdb on the Windows side. Skill `wsl-windows-exe`.

For usermode crashes: enable LocalDumps or attach before repro. Capture module list + exception code.

## Android native
1. `adb push` unstripped binary/`.so` or keep symbols locally + `set solib-search-path`
2. `adb shell run-as …` / restart app with wait-for-debugger as needed
3. `lldb` attach via NDK scripts or Android Studio
4. Always collect **tombstone** / `logcat` alongside debugger session

## What to capture in notes
```markdown
## Debug session
- Binary / build flags:
- Repro command:
- Symptom: crash | hang | wrong value
- Break / fault site:
- bt (trimmed):
- Root cause (one sentence):
- Fix:
```

## Hand-offs
- Can't build → `lab-build`
- Need a failing test first → `test-harness`
- Broader triage → `debug-triage`
- Crash in unknown malware → `malware-analysis` (don't debug ransomware on daily driver)

## Never
- Debug production third-party systems you don't own
- Commit huge core dumps into git
- Claim "fixed" without re-running the failing test/repro
