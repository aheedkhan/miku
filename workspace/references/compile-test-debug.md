# Compile → test → debug → iterate (WSL + Windows)

## Loop
1. **Build** PE on WSL (mingw) — `lab-build` + `wsl-windows-exe`
2. **Run** `.exe` (WSL interop smoke, then Win11 lab VM for Defender)
3. **Test** — one scripted success check — `test-harness`
4. **Fail?** → classify → `debug-triage` / **WinDbg on Windows** for PE (not gdb)
5. **Patch → rebuild → same test** — skill `lab-iterate`
6. Repeat until **success criteria** green

## Defender (only if criteria say so)
- Phase A: baseline on snapshotted Win11 (no evasion) — record Event IDs
- Phase B: one bypass technique per iteration + detection twin
- Phase C: done when agreed posture allows the PE + checkin

## Commands (WSL)
```bash
x86_64-w64-mingw32-gcc -g -O0 -o labrat.exe …
./labrat.exe
wslpath -w "$(pwd)/labrat.exe"   # path for Windows tools / VM share
```

## Rules
- Interop success ≠ Defender bypass
- Don’t change five knobs in one iteration
- No “fixed” without re-running the criteria commands
