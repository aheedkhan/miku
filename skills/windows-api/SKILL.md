---
name: windows-api
description: Learn and teach Windows API / NT internals — Win32, PE, services, registry, IPC, security. Store API cards in RAG from MSDN and primary docs.
---

# Windows API

## Goal
Build durable knowledge of **Windows APIs and NT internals**, then apply them in development, RE, malware analysis, and detection.

## When to use
- Win32 / NT API questions (CreateProcess, VirtualAlloc, Registry, services, Named Pipes, RPC, COM, …)
- PE structure, loaders, TLS callbacks, delay-load
- Tokens, SIDs, ACLs, integrity levels, UAC
- Kernel-user boundary (syscalls, ntdll, win32k) at a teaching level
- "How does malware abuse X API?" grounded in docs + known techniques

## Method
1. **RAG first** — search `workspace/os-internals/windows/` and
   `workspace/references/curated-links.md` (Win11, Defender, AMSI, ETW links).
2. **Primary docs** — learn.microsoft.com, Windows Internals concepts, ReactOS/Wine as secondary cross-checks. Never invent prototypes.
3. **API card** — save under `workspace/os-internals/windows/<topic>.md`.
4. **Teach** — signature → what it does → common flags → pitfalls → tiny example.
5. **Security link** — legitimate uses vs abuse patterns / telemetry (ETW, Sysmon) when relevant.
6. **Index** — `hermes workspace index` after new cards.

## API card template
```markdown
# <API or subsystem>
- Headers / libs:
- Prototype (cite MSDN):
- Ring / privilege notes:
- Related APIs:
- Common flags / structs:
- Failure modes:
- Example (minimal):
- Malware / detection angle (optional):
- Sources (URL + date):
```

## Prefer
- Accurate calling conventions and error handling (`GetLastError`, NTSTATUS).
- Distinguish Win32 vs Native API (`Nt*` / `Zw*`) clearly.
