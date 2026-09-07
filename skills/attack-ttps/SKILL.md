---
name: attack-ttps
description: >-
  ATT&CK / TTP expertise for authorized labs — map behaviors to technique IDs,
  pick implementable mechanisms, build one technique at a time, and always ship
  a detection twin. Use for "what TTPs", technique labs, kill-chain design,
  or mapping a RAT/malware module to MITRE.
---

# ATT&CK / TTP playbook (authorized lab)

## Goal
Make Miku fluent in **techniques, tactics, and procedures**: choose the right TTP,
explain the mechanism, implement a **minimal lab demo**, map ATT&CK IDs, and write
detections. Pair every offensive build with analyst thinking.

**Scope:** User-owned VMs / explicit pentest only. Never optimize TTPs for third-party victims.

## When to use
- "What TTPs for a RAT / loader / persistence?"
- "Map this behavior to ATT&CK"
- "Teach / implement technique X"
- Kill-chain or module roadmap before coding
- Post-build: tag what we just shipped with IDs + detection twins

## Always load first
1. RAG: `workspace/references/attack-ttp-catalog.md`
2. RAG: `workspace/os-internals/windows/win32-injection-map.md` (if inject/load)
3. Skills: `malware-authoring` (build) → platform skill (`windows-rat-dev` / `android-malware-*` / `linux-internals`)
4. Prior art: `github-explore` for real implementations (read, don't copy blindly)

## Operating contract (non-negotiable)

For **every** technique lab or module:

| Step | Output |
|------|--------|
| 1. Tactic | e.g. Persistence, Defense Evasion, C2 |
| 2. Technique ID(s) | Primary `Txxxx` + sub-technique if known |
| 3. Mechanism | APIs / OS objects / data flow in plain language |
| 4. Lab demo | Smallest code under `labs/techniques/<os>/<t-id>-<slug>/` |
| 5. Success criteria | Observable proof (log, process tree, network, file) |
| 6. Detection twin | Sysmon/ETW/YARA/Sigma/Defender idea — at least one |
| 7. Notes | `workspace/malware-authoring/techniques/<t-id>-<slug>.md` |

Never dump 10 TTPs as unfinished code. **One technique → green criteria → next.**

## Kill-chain template (Windows implant example)

Use this when designing a full RAT path; implement modules in this order unless user overrides:

1. **Initial access (lab)** — dropper / USB / shared folder (T1204) — *manual delivery OK*
2. **Execution** — CreateProcess / rundll / script host (T1059)
3. **Persistence** (optional module) — Run key / schtask / service (T1547 / T1053 / T1543)
4. **Defense evasion** (separate phase) — AMSI/ETW/unhook (T1562.*) — only if criteria say so
5. **Discovery** — processes, files, system info (T1057 / T1083 / T1082)
6. **Collection** — clipboard / screenshot / files (T1113 / T1005) as *scoped modules*
7. **C2** — HTTP(S) beacon (T1071) + jitter (T1029)
8. **Exfiltration** — same channel or dedicated (T1041)
9. **Impact** — usually **out of scope** for research RATs (document non-goals)

## How to answer "what TTPs should we use?"

1. Ask / infer **objective** (beacon only vs full post-ex vs detection research)
2. Pick **minimal set** from catalog that hits the objective
3. Table: Tactic | Technique | Why | Lab order | Detection twin
4. Hand off coding to `malware-authoring` / `windows-rat-dev` with that table as the roadmap

## Technique → skill routing

| Family | Route |
|--------|-------|
| Win implant / C2 / inject / persist | `windows-rat-dev` + `windows-api` |
| Generic technique demo | `malware-authoring` |
| Android | `android-malware-dev` |
| Linux implant / LD_PRELOAD / cron | `linux-internals` + `malware-authoring` |
| CVE as initial access | `cve-malware-test` |
| Analyze observed TTPs on a sample | `malware-analysis` |

## ATT&CK mapping quality bar

- Prefer **specific** IDs (`T1547.001` Run key) over bare tactics
- If unsure of sub-technique: state parent + `[UNVERIFIED]` sub-id until confirmed
- Procedures = *how we did it in this lab* (language, APIs, paths) — write that in the technique note
- Cite MITRE pages via `web_fetch` when teaching or writing reports

## Anti-patterns
- Listing 30 ATT&CK IDs with no build plan
- Evasion before a working clear-text beacon
- Skipping detection twins
- Claiming "FUD" / "undetectable on real endpoints"
