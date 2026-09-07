# Win32 process injection map (lab reference)

Research / authorized VM only. Document target process and snapshot before tests.

## Common user-mode patterns

| Pattern | Typical APIs | Notes |
|---------|--------------|-------|
| Remote thread | `OpenProcess`, `VirtualAllocEx`, `WriteProcessMemory`, `CreateRemoteThread` | Classic; noisy |
| APC | `QueueUserAPC` + alertable wait | Needs suitable thread state |
| Section map | `NtCreateSection`, `NtMapViewOfSection` | Cross-process mapping |
| Early bird | Queue APC before main thread runs | Timing-sensitive |
| Module stomping | Write into existing module RX | Breaks some integrity checks |

## What to capture every run

- Target PID / image name
- HVCI / Memory integrity on/off
- Defender cloud on/off
- Sysmon Event IDs (8, 10, 25 if configured)
- Whether Smart App Control blocked the dropper

## Safer lab progression

1. Self-inject into own process (prove primitives)
2. Inject into a lab helper process you own
3. Only then try higher-value targets — still inside the snapshot VM

## Detection twin starters

- Sysmon 8 (CreateRemoteThread) / 10 (ProcessAccess)
- ETW `Microsoft-Windows-Threat-Intelligence` where available
- Memory scanner hits on RWX private pages in remote process
