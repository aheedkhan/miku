# WSL → Windows lab guide (spoon-feed friendly)

How you and **Miku** share work when building/testing Windows `.exe` research labs
(RAT/CVE harnesses) from WSL Ubuntu.

Say **`spoon-feed`** or **`hold my hand`** anytime — she switches to step-by-step
commands you paste, and waits for your output before the next step.

---

## Big picture

```
YOU                          MIKU
─────────────────────        ────────────────────────────────
Win11 lab VM / snapshot      Writes code under labs/
Approve sudo when asked      mingw-builds labrat.exe in WSL
Paste command output         Runs tests, reads errors
Hyper-V / share / copy PE    Patches → rebuild → same test
Say the SUCCESS GOAL         Loops (lab-iterate) until criteria pass
```

She is the engineer in the terminal. You own the Windows box and approvals.

---

## Modes

| You say | She does |
|---------|----------|
| *(default)* | Acts: edit, build, test; asks only when stuck/sudo/VM |
| **`spoon-feed`** / **`hold my hand`** | One step at a time; exact command; waits for your paste-back |
| **`just do it`** | Maximum autonomy in WSL; still asks for VM/Defender actions she can’t click |
| **`Defender in scope`** | Adds baseline → bypass phases on **snapshotted Win11 lab only** |

---

## First-time setup checklist

**Full Windows 11 lab from zero (A→Z):**  
→ [`windows11-lab-setup-atoz.md`](windows11-lab-setup-atoz.md)  
Say `spoon-feed Windows lab` — Miku walks letter by letter.

### A. WSL (Linux side) — once
```bash
git clone https://github.com/aheedkhan/miku.git && cd miku
./install-wsl.sh
source .venv/bin/activate && miku
```

### B. Windows 11 lab VM — once
Follow A→Z doc (hypervisor → ISO → snapshot → host IP → firewall → copy `.exe`).
Minimal: snapshotted Win11 guest + guest can `Test-NetConnection` to host:8080.

---

## Happy path (protocol only, no Defender)

1. Miku scaffolds / edits `labs/rat/win11/labrat/`
2. `make` → `labrat.exe` (mingw)
3. Start C2 on WSL: `python3 …/c2_server.py --host 0.0.0.0 --port 8080`
4. Set `C2_HOST` to an IP the runner can reach
5. Run `./labrat.exe` from WSL **or** copy into VM and run
6. Fail? → she reads the error → patch → rebuild → **same** test (`lab-iterate`)
7. Pass checkin + shell → done for this phase

## Defender path (only if you ask)

1. Snapshot VM  
2. **Baseline**: run current PE with **no** evasion — record Defender Event IDs  
3. **Bypass**: one change per loop + detection twin  
4. Green only when *your* criteria say so  

Interop on the host ≠ “Defender bypassed.”

---

## What to paste back when spoon-feeding

When she gives a command, reply with:
```
EXIT: <code>
OUT:
<paste stdout/stderr>
```
Or a screenshot description of a Defender toast / Event Viewer line.

---

## Skills she should load (you can ask)

| Phase | Skill |
|-------|--------|
| WSL PE build/run | `wsl-windows-exe` |
| Until criteria pass | `lab-iterate` |
| Compile errors | `lab-build` |
| Crash stacks | `debugger` (WinDbg for `.exe`) |
| RAT design | `windows-rat-dev` |
| CVE harness | `cve-malware-test` |

Or: *“use_skill lab-iterate and spoon-feed me.”*

---

## Safety

- Lab / owned VMs only  
- No third-party targeting  
- Don’t commit `.exe` (gitignored)  
- Daily-driver host: fine for compile + light interop; **Defender claims → lab VM**
