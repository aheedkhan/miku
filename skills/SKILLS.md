# Skills index (Miku / Hermes)

Load a playbook mid-chat with the `use_skill` tool (or `/skill <name>` in the REPL).
Names below are what the model sees in the system prompt.

## Core loop
| Skill | Use when |
|-------|----------|
| `session-ops` | Session start/end, what were we doing |
| `research-pipeline` | Multi-source investigation → notes → report |
| `knowledge-rag` | Save/search durable notes; CVE index commands |
| `browsing` | web_search + web_fetch discipline |
| `github-explore` | Hunt prior art / read repos on GitHub |
| `lab-hygiene` | Isolation, secrets, no binaries in git |
| `lab-build` | Compile / link / Debug+ASAN flags |
| `wsl-windows-exe` | Build/run PE `.exe` from WSL; WinDbg on Windows |
| `lab-iterate` | Error→debug→fix until criteria (Defender lab phases) |
| `test-harness` | Red→green checks; CVE/detection harnesses |
| `debug-triage` | Classify build vs runtime; evidence trail |
| `debugger` | gdb (ELF) / WinDbg (PE) / lldb / Android |
| `report-generation` / `pdf-creation` | Deliverables |
| `code-review-git` | Diff review + commit/PR hygiene |
| `adr-decisions` | Lock long-lived choices |
| `teaching-lab` | Teach **or spoon-feed** (one step, wait for output) |
| `env-bootstrap` | Broken install / Ollama / WSL |

## Security research
| Skill | Use when |
|-------|----------|
| `cve-research` | Triage CVE / advisory / patch |
| `cve-malware-test` | Build lab harness for a CVE |
| `daily-android-cve` | Daily Android/CVE digest |
| `malware-authoring` | Design/build malware (lab) |
| `malware-analysis` | Triage unknown samples |
| `malware-intel` | Family cards / MalwareBazaar |
| `windows-rat-dev` | Win11 implant / C2 lab |
| `windows-api` | Win32/NT API detail |
| `linux-internals` | Kernel/userland Linux |
| `android-internals` | AOSP / framework security model |
| `android-malware` / `android-malware-dev` / `android-malware-analysis` | Android offense/defense RE |

## Tools (not skills — always available)
`rag_query`, `rag_remember`, `web_search`, `web_fetch`, `github` (explore + PR/issue),
`cve_lookup`, malware bazaar, `android`, `git_*`, `fs_*`, `shell_exec`, `use_skill`, subagents.
