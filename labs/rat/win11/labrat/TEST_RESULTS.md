# labrat test results

Saved: 2026-09-02

## Integration tests (Linux — protocol simulator)

Command:
```bash
cd labs/rat/win11/labrat/server && python3 run_tests.py
```

Result: **8 passed, 0 failed**

| Test | Status |
|------|--------|
| v0.1 checkin | PASS |
| v0.2 shell | PASS |
| v0.3 download | PASS |
| v0.3 upload | PASS |
| v0.3 upload bytes | PASS |
| v0.4 inject | PASS |
| v0.4 persist | PASS |
| v0.5 evasion hook | PASS (protocol only; ETW patch not exercised on Win11) |

## Build status

| Item | Status |
|------|--------|
| C implant source | complete v0.1–v0.5 in single binary |
| `labrat.exe` | not built — `mingw64-gcc` not installed on dev host |
| Win11 VM test | **pending** |
| Defender baseline | **pending** |
| Phased builds (v01–v05 separate) | **pending** — do later |

## Phase assessment

- **Code version:** v0.5 (evasion code included: XOR C2 host, `EtwEventWrite` patch)
- **Testing phase:** pre-Win11 baseline — treat as v0.1 protocol verified only
- **Evasion phase:** code present; proper evasion testing deferred until Win11 baseline runs

## Next steps (later)

1. `sudo dnf install mingw64-gcc mingw64-winpthreads`
2. Split builds: `EVASION=0` for v0.1–v0.4 baseline, `EVASION=1` for v0.5
3. Win11 VM: snapshot → run each phase → document Defender Event IDs
4. Record analyst hash in `workspace/malware-authoring/rat/projects/labrat.md` (VM only)
