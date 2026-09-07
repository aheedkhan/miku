---
name: wsl-windows-exe
description: >-
  Run and test Windows .exe from WSL — interop, mingw cross-build, paths,
  copying into Win11 lab VM, Windows-side debugging. Use when building PE
  implants on WSL Ubuntu and executing/testing them on Windows.
---

# WSL ↔ Windows .exe lab

## Goal
On **WSL2 (Ubuntu/Debian on Windows)**: cross-compile PE (`.exe`), run it via WSL interop
and/or copy into an isolated **Win11 lab VM**, then debug with Windows tools.

## Mental model
| Where | What runs |
|-------|-----------|
| WSL Linux | `x86_64-w64-mingw32-gcc`, make, git, Hermes, C2 server (Python) |
| Windows host (interop) | `./labrat.exe` from `/mnt/c/...` or WSL cwd — real PE, real Win32 |
| Win11 **lab VM** | Final Defender / HVCI tests (snapshot first) |

WSL can launch `.exe` when Windows interop is enabled (`/.wslconfig` / default on most installs).
That is **not** Wine — it is the Windows loader.

## Build PE from WSL
```bash
# toolchain (install-wsl.sh includes mingw-w64)
x86_64-w64-mingw32-gcc --version

cd labs/rat/win11/<project>/implant
make    # should invoke mingw; produce labrat.exe
file labrat.exe   # PE32+ executable
```

Debug build flags (symbols for WinDbg):
```bash
x86_64-w64-mingw32-gcc -g -O0 -o labrat.exe … 
# or keep a parallel labrat_debug.exe
```

## Run .exe from WSL
```bash
# from the directory containing the PE
./labrat.exe
# or explicit
cmd.exe /c labrat.exe
powershell.exe -NoProfile -Command ".\labrat.exe"

# Windows path of current WSL file
wslpath -w "$(pwd)/labrat.exe"
```

C2 on WSL listening for host/VM:
- Bind `0.0.0.0`, not only `127.0.0.1`
- From Windows host interop, `localhost` may reach WSL via mirrored/localhost forwarding (WSL2 version-dependent) — **verify** with a quick curl/checkin
- From a **Hyper-V / VMware guest**, use the host LAN IP / vEthernet IP documented in the project card

## Copy into Win11 lab VM
Prefer one clean path and stick to it:
1. Shared folder / `\\wsl$\<Distro>\home\…\labrat.exe`
2. Or HTTP from WSL C2 / python `-m http.server` on lab LAN
3. Snapshot VM **before** first run

## Windows debugging (when .exe misbehaves)
On **Windows host or lab VM** (not gdb inside WSL for PE):
| Tool | Use |
|------|-----|
| **WinDbg / cdb** | Crash stacks, breakpoints on PE |
| **Visual Studio** | Source-level if PDB produced |
| **Procmon / API Monitor** | Fail paths, file/reg/network |
| **DebugView** | OutputDebugString |
| **Event Viewer** | Defender Operational log |

PDB with mingw is limited — for deep source debug prefer MSVC on Windows, or rely on Procmon + logging you add to the implant.

Quick cdb attach/repro (lab VM):
```text
cdb -g -G labrat.exe
# on crash: k ; r ; !analyze -v
```

## Defender-aware test placement
- **Smoke / protocol**: WSL-built `.exe` + local C2 (interop or VM) — skill `test-harness`
- **Defender baseline / bypass**: **only** on snapshotted Win11 lab VM — skill `lab-iterate` + `windows-rat-dev`
- Never “test Defender” on the daily-driver host without an explicit lab snapshot story

## Spoon-feed
If the user is lost on VM/share/Defender clicks, switch to skill `teaching-lab`
(`spoon-feed`) and follow `docs/wsl-windows-lab-guide.md` — one command per turn.

## Hand-offs
| Need | Skill |
|------|-------|
| Iterate until requirement met | `lab-iterate` |
| gdb vs WinDbg choice | `debugger` |
| RAT design / phases | `windows-rat-dev` |
| Compile errors | `lab-build` |

## Never
- Treat WSL interop success as Defender-bypass success
- Commit `.exe` / PDBs into git (`labs/**/*.exe` ignored)
- Run untrusted PE outside a disposable VM
