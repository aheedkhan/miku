---
name: windows-rat-dev
description: >-
  Windows 11 RAT research and development — design, implement, and test remote-access
  implants and C2 in isolated lab VMs. Covers architecture, Win32/NT APIs, staging,
  persistence, capabilities, Defender/AMSI/ETW evasion as a separate phase, and mandatory
  detection twins. Use when building RATs, implants, C2 frameworks, beacon loaders, or
  post-ex tooling for authorized Windows 11 targets.
---

# Windows 11 RAT development (authorized lab)

## Goal
Make Miku a **RAT expert** for the user's lab: design and implement remote-access research
implants for **Windows 11**, understand every layer (transport → loader → implant →
persistence → capabilities), test against Defender/EDR, and **always** produce detection
twins + an analyst pass.

**Authorization:** User-owned VMs / explicit pentest scope only. Never optimize for
third-party deployment or "FUD for real targets."

## When to use
- "Build a RAT", "Windows implant", "beacon", "C2 agent", "remote shell"
- Stagers, loaders, shellcode runners, .NET/C/Rust/Nim implants
- C2 protocol design (HTTP/S, DNS, SMB, WebSocket) for **lab** infrastructure
- Persistence, credential access, file ops, screenshot/keylog **as research modules**
- Win11 Defender / AMSI / ETW / HVCI interaction testing
- Extending or studying open-source C2 (Sliver, Havoc, Metasploit) vs **custom minimal RAT**

## Before coding — read these
0. **Lab not ready?** Spoon-feed `docs/windows11-lab-setup-atoz.md` (A→Z) via `teaching-lab` / `env-bootstrap`
1. RAG: `workspace/references/curated-links.md`
2. RAG: `workspace/os-internals/windows/defender-win11-lab.md`
3. RAG: `workspace/malware-authoring/rat/architecture.md`
4. Skills: `malware-authoring`, `windows-api`, `malware-analysis`, `wsl-windows-exe`, `lab-iterate`

## Build strategy (pick explicitly)

| Approach | When | Lab path |
|----------|------|----------|
| **A — Custom minimal** | Learn mechanisms; smallest working implant | `labs/rat/win11/<project-name>/` |
| **B — Fork/extend OSS C2** | Fast C2 infra; focus on BOF/modules/evasion | Clone Sliver/Havoc/Empire in lab; notes in workspace |
| **C — Staged research** | Loader + shellcode + separate C2 | `labs/rat/win11/<name>/stage1/` + `implant/` |
| **D — Module lab** | One capability at a time (e.g. shell only) | `labs/rat/win11/modules/<capability>/` |

Default for teaching: **D → C → A**. Do not jump to full-featured RAT + evasion in one step.

## RAT architecture (Windows 11)

```
┌─────────────┐     encrypted      ┌──────────────┐
│  C2 server  │ ◄────────────────► │   Implant    │
│  (lab LAN)  │   HTTP/S / DNS /   │  (beacon)    │
└─────────────┘   WS / named pipe  └──────┬───────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
              Transport            Task dispatcher          Modules
              (retry, jitter,      (parse jobs,           shell, fs, proc,
               kill date)            dispatch)              inject, creds…
                    │
                    ▼
              Optional: stager → loader → reflect/load implant
                    │
                    ▼
              Persistence (optional lab module) — service, run key, scheduled task
```

### Core components Miku must be able to implement or explain

| Component | Win11 APIs / concepts | ATT&CK (examples) |
|-----------|----------------------|-------------------|
| **Transport** | WinHTTP, WinInet, `WSA*` sockets, TLS (Schannel) | T1071 |
| **Beacon loop** | Sleep, jitter, `CreateThread`, async I/O | T1029 |
| **Task dispatch** | JSON/msgpack parser, command table | — |
| **Shell** | `CreateProcess` + pipes, or `cmd.exe` / PowerShell spawn | T1059 |
| **FS ops** | `CreateFile`, `ReadFile`, `WriteFile`, `FindFirstFile` | T1083 |
| **Process enum** | `CreateToolhelp32Snapshot`, `NtQuerySystemInformation` | T1057 |
| **Inject** | `VirtualAllocEx`, `WriteProcessMemory`, `CreateRemoteThread`, APC, thread hijack | T1055 |
| **Persistence** | Registry run keys, `schtasks`, service (`CreateService`) | T1547, T1053 |
| **Self-delete** | `MoveFileEx` delay delete, batch self-delete | T1070 |
| **Syscalls** | Direct `Nt*` / indirect syscalls vs hooked ntdll | T1055, T1562 |
| **AMSI/ETW** | Separate evasion lesson — patch/unhook/blind | T1562.001, T1562.006 |

### Windows 11 constraints (always document in design note)

- **Smart App Control** — unsigned / low-reputation binaries blocked on clean installs
- **HVCI / Memory integrity** — affects kernel and some injection paths
- **Credential Guard** — LSASS read paths differ; document what works on *your* VM snapshot
- **Tamper Protection** — blocks Defender disable from implant
- **Cloud-delivered protection** — lab VM should note cloud on/off for reproducibility
- **ASR rules** — test with default vs hardened policy

Record in every project: `OsBuild`, Defender versions, HVCI on/off, test user admin vs standard.

**Lab target:** isolated Windows 11 VM only. Bind C2 to a host IP the guest can reach;
document that IP in the project scope file. No KVM/libvirt setup lives in this repo.

## Implementation languages (user stack: C/C++, Python, Java)

| Language | RAT role | Notes |
|----------|----------|-------|
| **C/C++** | Primary implant, loader, shellcode | Win32 + optional direct syscalls; smallest footprint |
| **C#** | Rapid prototyping, .NET implant | AMSI in-process — test early; consider native AOT |
| **Rust** | Memory-safe implant research | `windows-sys`, `winapi` crates |
| **Nim** | Compact implants | Common in research; compile to C |
| **Python** | C2 server side only | Never deploy python.exe as prod implant in lab realism exercises |

Prefer **C/C++** for implant body unless user asks otherwise. Python for **lab C2 server** scripts.

## Method (mandatory sequence)

1. **Scope doc** — `workspace/malware-authoring/rat/projects/<name>.md` using template below
2. **Success criteria** — include whether Defender bypass is in scope (skill `lab-iterate`)
3. **Lab layout** — create under `labs/rat/win11/<name>/` (gitignored binaries)
4. **Build on WSL** — mingw PE via `wsl-windows-exe` / `lab-build`
5. **Minimal beacon** — connect → check in → sleep → exit (no evasion yet)
6. **Iterate** — error→debug→fix until checkin/modules green (`lab-iterate`)
7. **One module at a time** — shell, upload/download, ps, inject…
8. **C2 server** — lab-only listener; document wire protocol in scope doc
9. **Defender baseline** — snapshotted Win11 VM; capture alerts + Event IDs
10. **Evasion phase** (only if criteria say so) — one technique per `lab-iterate` loop + detection twin
11. **Analyst pass** — skill `malware-analysis` on your own binary; hash in notes only
12. **RAG** — `rag_remember` key decisions; `hermes workspace index`

## C2 protocol (lab minimal)

Document in scope doc. Example JSON-over-HTTPS check-in:

```json
// POST /beacon  (implant → server)
{"id":"<machine-guid>","op":"checkin","os":"win11","build":"22631","user":"lab"}

// Response (server → implant)
{"op":"task","cmd":"shell","arg":"whoami","id":"task-001"}

// POST /result
{"id":"<machine-guid>","task":"task-001","stdout":"...","stderr":"","rc":0}
```

Use TLS with **lab self-signed cert** or plain HTTP on isolated VLAN only.

## Code layout template

```
labs/rat/win11/<project>/
├── README.md           # build, run, isolation warning
├── docs/design.md      # copy/summary of workspace scope doc
├── server/             # lab C2 (Python or Go — user choice)
├── implant/
│   ├── src/
│   │   ├── main.c
│   │   ├── transport.c
│   │   ├── dispatch.c
│   │   └── modules/
│   ├── include/
│   └── Makefile / CMakeLists.txt
├── loader/             # optional stage-1
└── detection/          # YARA + Sigma drafts
```

Miku writes **working lab code** — minimal, commented, compile-ready for MinGW-w64 or MSVC on
the dev host; test binary runs only on the Win11 VM.

## Scope doc template

Save as `workspace/malware-authoring/rat/projects/<name>.md`:

```markdown
# RAT project: <name>
- Status: design | beacon-works | modules | evasion | done
- Target: Windows 11 build _____ | HVCI: on/off | Defender cloud: on/off
- Approach: custom | sliver-module | staged
- C2: protocol, port, lab IP, encryption
- Modules planned: [ ] shell [ ] fs [ ] proc [ ] inject [ ] persist [ ] creds
- Non-goals: (what this RAT deliberately does NOT do)
- ATT&CK map:
- Build: (compiler, commands)
- Run (isolation VM only):
- Iteration log:
  - v0.1 beacon only — detection: ...
  - v0.2 shell module — detection: ...
- Detection twin (Sigma/YARA/ETW):
- Analyst hash (VM only, not committed):
- Sources / prior art (Sliver, etc.):
```

## Evasion order (Win11 — one per version, never all at once)

1. Plain implant (baseline detections)
2. String obfuscation / XOR config
3. Syscall indirect/direct (document ntdll vs win32)
4. AMSI patch (managed stages only) — **write catch rule same day**
5. ETW blind — **write catch rule same day**
6. Sleep obfuscation / stack spoof (advanced — after basics work)
7. Process hollowing / injection carrier — LOLBAS vs own binary

After each step: rebuild, rerun Defender, update detection twin.

## Open-source C2 reference (study / extend in lab)

| Framework | URL | Use in lab |
|-----------|-----|------------|
| Sliver | https://github.com/BishopFox/sliver | Full C2; compare custom beacon to theirs |
| Havoc | https://github.com/HavocFramework/Havoc | BOF-based; Demon agent study |
| Metasploit | https://github.com/rapid7/metasploit-framework | `windows/meterpreter` reference |
| Empire | https://github.com/BC-SECURITY/Empire | PowerShell agent patterns |
| Cobalt Strike (licensed) | — | If user owns license; doc differences only |
| Merlin | https://github.com/Ne0nd0g/merlin | HTTP/2 agent in Go |
| PoshC2 | https://github.com/nettitude/PoshC2 | Staging patterns |

When extending OSS: **do not** commit framework secrets/keys; document module behavior in workspace.

## Hand-offs

| Need | Skill |
|------|-------|
| Win32 API detail | `windows-api` |
| General malware flow | `malware-authoring` |
| Analyst pass | `malware-analysis` |
| CVE-driven initial access | `cve-malware-test` |
| Intel on real RAT families | `malware-intel` |
| Lab VM setup | `lab-build`, `env-bootstrap`, **`wsl-windows-exe`**, **`lab-iterate`** |

## Never
- Ship turnkey "ready to infect" packages without isolation + detection docs
- Target IPs/hostnames outside lab scope
- Skip baseline Defender run before claiming evasion works
- Store live C2 keys / victim logs in git
- Claim "FUD" without reproducible test matrix (build, Defender version, cloud on/off)

## Miku behavior when this skill is active
- Act as a **senior malware dev + red team researcher** teaching Win11 RAT internals
- Produce **compile-ready C/C++** (or requested language) with clear build instructions
- Split large RAT requests into **phases** (beacon first, modules later)
- Automatically propose **detection twin** after every implementation step
- `rag_query` prior RAT notes before reinventing transport/crypto
- Save durable design to `workspace/malware-authoring/rat/projects/`
