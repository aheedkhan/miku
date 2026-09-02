# Curated reference links — malware dev, CVEs, Windows 11, Defender/EDR

> **Scope:** Authorized lab / FYP / malware-analysis research only. Use isolated VMs,
> never against third-party systems. Miku indexes this file into RAG — search with
> `rag_query` or `hermes workspace search "defender amsi"`.

Last updated: 2026-09-02

---

## CVE & vulnerability intelligence (open source / free)

| Resource | URL | Notes |
|----------|-----|-------|
| **NVD** (US gov) | https://nvd.nist.gov/ | Primary CVE metadata, CVSS, CWE; Hermes `cve_lookup` uses this + OSV |
| **OSV** (Google) | https://osv.dev/ | Open-source package vulns; good for library/CVE cross-ref |
| **MITRE CVE list** | https://cve.mitre.org/ | Canonical CVE IDs |
| **GitHub Advisories** | https://github.com/advisories | GHSA IDs for repos you track |
| **CISA KEV** | https://www.cisa.gov/known-exploited-vulnerabilities-catalog | Actively exploited in the wild — prioritize these |
| **Vulners** | https://vulners.com/ | Aggregator; useful for exploit/PoC cross-links |
| **Exploit-DB** | https://www.exploit-db.com/ | Public PoC/exploit archive — verify against vendor patches |
| **0day.today** (mirror caution) | https://0day.today/ | Secondary; prefer NVD + vendor advisories first |
| **Android Security Bulletins** | https://source.android.com/docs/security/bulletin | Monthly ASB — pair with `daily-android-cve` skill |
| **Microsoft MSRC** | https://msrc.microsoft.com/update-guide/vulnerability | Windows/Defender/Edge patch Tuesday |
| **ProjectDiscovery Nuclei templates** | https://github.com/projectdiscovery/nuclei-templates | Open-source scanner templates by CVE/product |
| **Google OSV Scanner** | https://github.com/google/osv-scanner | CLI to scan deps against OSV |
| **Vulncheck** (free tier) | https://vulncheck.com/ | KEV + exploit intel overlay |

### CVE workflow in this repo
- Lookup: `cve_lookup` tool or skill `cve-research`
- Save notes: `workspace/cves/CVE-YYYY-NNNN.md`
- Lab harness: `labs/cve-tests/windows/` + skill `cve-malware-test`
- Auto-ingest: `/refresh` pulls recent Android CVEs into RAG

---

## Malware development & analysis (research / education)

| Resource | URL | Notes |
|----------|-----|-------|
| **MITRE ATT&CK** | https://attack.mitre.org/ | Technique taxonomy — map every sample to T-codes |
| **MITRE ATT&CK — Evade** | https://attack.mitre.org/tactics/TA0005/ | Defense evasion tactics (AMSI, obfuscation, etc.) |
| **MalwareBazaar** | https://bazaar.abuse.ch/ | Sample metadata + hashes; Hermes `malware_intel` tool |
| **VX Underground** | https://vx-underground.org/ | Papers, samples archive (research community) |
| **Awesome Malware Analysis** | https://github.com/rshipp/awesome-malware-analysis | Curated tool/paper list |
| **Malware Development Guide** | https://github.com/Meowmycks/MalwareDevelopmentGuide | Educational Windows malware dev concepts |
| **Red Teaming / OffSec list** | https://github.com/EndlessLoop786/RedTeaming-OffensiveSecurity | Broader offensive tooling index |
| **theZoo (archived samples)** | https://github.com/ytisf/theZoo | **Isolated VM only** — historical malware for analysis |
| **Malware Source Code mirror** | https://github.com/vxunderground/MalwareSourceCode | RE reference — never run on host OS |
| **ANY.RUN public submissions** | https://app.any.run/submissions | Live sandbox reports (behavioral) |
| **Hybrid Analysis** | https://www.hybrid-analysis.com/ | Free sandbox lookups by hash |
| **VirusTotal** | https://www.virustotal.com/ | Multi-AV + behavior; API optional |
| **Unprotect.it** | https://unprotect.it/ | Anti-analysis / packer / evasion encyclopedia |
| **Shellcode / PIC repos** | https://github.com/wbenny/mini-shellcode | Position-independent code examples |
| **Donut (shellcode generator)** | https://github.com/TheWover/donut | PE→shellcode loader research |
| **Unicorn (shellcode emulator)** | https://github.com/trustedsec/unicorn | Test shellcode without full execution |

### Repo layout for your work
- Design notes: `workspace/malware-authoring/`
- Built samples: `labs/` (binaries gitignored)
- Detection twins: YARA/Sigma ideas in the same note as the build

---

## Windows 11 — internals, security features, RE

| Resource | URL | Notes |
|----------|-----|-------|
| **Win32 API docs** | https://learn.microsoft.com/en-us/windows/win32/ | Primary API reference — skill `windows-api` |
| **Windows 11 release health** | https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information | Build numbers, LTSC, servicing |
| **Windows security docs** | https://learn.microsoft.com/en-us/windows/security/ | VBS, HVCI, Credential Guard, Smart App Control |
| **Virtualization-based security** | https://learn.microsoft.com/en-us/windows/hardware/design/device-experiences/oem-vbs | VBS / hypervisor-protected code integrity |
| **HVCI (Memory integrity)** | https://learn.microsoft.com/en-us/windows/security/hardware-security/enable-virtualization-based-protection-of-code-integrity | Blocks unsigned kernel code |
| **Smart App Control** | https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/overview | Win11 app reputation / blocking |
| **PE format** | https://learn.microsoft.com/en-us/windows/win32/debug/pe-format | Essential for loaders/packers |
| **Windows Internals (book hub)** | https://learn.microsoft.com/en-us/sysinternals/resources/windows-internals | Concept index |
| **Vergilius Project** | https://www.vergiliusproject.com/ | Kernel struct layouts by Windows build |
| **hfiref0x Windows Internals notes** | https://github.com/hfiref0x/WindowsInternals | Community RE notes |
| **ReactOS / Wine headers** | https://github.com/wine-mirror/wine | Secondary prototype cross-check |
| **Windows Driver Samples** | https://github.com/microsoft/Windows-Driver-Samples | Kernel/driver reference code |
| **Sysinternals Suite** | https://learn.microsoft.com/en-us/sysinternals/ | Procmon, Autoruns, Process Explorer |
| **WinDbg docs** | https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/ | User + kernel debugging |

### Windows 11 build tracking
- Note your lab build: `winver`, `systeminfo`, or `[Environment]::OSVersionVersionString`
- HVCI on/off changes exploit surface — document in every harness note

---

## Windows Defender, AMSI, ETW & EDR research (authorized lab)

Understanding *how* Defender works is prerequisite to building **detection twins** and
testing samples in isolation — not for deploying against real victims.

| Resource | URL | Notes |
|----------|-----|-------|
| **Microsoft Defender AV** | https://learn.microsoft.com/en-us/microsoft-365/security/defender-endpoint/microsoft-defender-antivirus-windows | Architecture, scans, cloud protection |
| **AMSI (Anti-Malware Scan Interface)** | https://learn.microsoft.com/en-us/windows/win32/amsi/antimalware-scan-interface-portal | Script/content scanning API — key for PowerShell/.NET research |
| **ETW (Event Tracing for Windows)** | https://learn.microsoft.com/en-us/windows/win32/etw/event-tracing-portal | Telemetry backbone — Defender + EDR rely on this |
| **LOLBAS** | https://lolbas-project.github.io/ | Living-off-the-land binaries — abuse + detection |
| **LOLBAS GitHub** | https://github.com/LOLBAS-Project/LOLBAS | Same, searchable |
| **GTFOBins (Linux counterpart)** | https://gtfobins.github.io/ | For cross-platform labs |
| **Atomic Red Team** | https://github.com/redcanaryco/atomic-red-team | Runnable ATT&CK technique tests — map to Defender alerts |
| **Sigma rules** | https://github.com/SigmaHQ/sigma | Detection rule corpus |
| **Elastic detection rules** | https://github.com/elastic/detection-rules | EDR-style detections |
| **Neo23x0 signature-base** | https://github.com/Neo23x0/signature-base | YARA + IOC collections |
| **Threat Hunter Playbook** | https://github.com/OTRF/ThreatHunter-Playbook | Hypothesis-driven hunting |
| **MITRE D3FEND** | https://d3fend.mitre.org/ | Defensive countermeasures mapped to ATT&CK |

### Open-source offensive research tools (lab VMs only)

Use to **generate telemetry** and validate detections — pair every run with Sigma/YARA ideas.

| Tool | URL | Typical research use |
|------|-----|----------------------|
| **Metasploit** | https://github.com/rapid7/metasploit-framework | Exploit modules, payload staging research |
| **Empire / Starkiller** | https://github.com/BC-SECURITY/Empire | Post-ex staging, script agents |
| **Sliver C2** | https://github.com/BishopFox/sliver | Modern C2 framework for red-team labs |
| **Havoc** | https://github.com/HavocFramework/Havoc | C2 + BOF research |
| **Mimikatz** | https://github.com/gentilkiwi/mimikatz | Credential material research — **never on real domain** |
| **Rubeus** | https://github.com/GhostPack/Rubeus | Kerberos abuse research |
| **Seatbelt** | https://github.com/GhostPack/Seatbelt | Host enumeration |
| **SharpCollection** | https://github.com/Flangvik/SharpCollection | Precompiled .NET tools for lab snapshots |
| **Nim / Rust offensive templates** | https://github.com/byt3bl33d3r/OffensiveNim | Alternative implant languages |
| **ScareCrow** | https://github.com/optiv/ScareCrow | Loader/shellcode packaging research |
| **Freeze** | https://github.com/optiv/Freeze | Suspended-process injection research |
| **Inceptor** | https://github.com/klezVirus/inceptor | Template-based PE/shellcode builder |

### Defender evasion *concepts* (study → detection, not deployment)

| Topic | Primary doc / research entry | What to document in your notes |
|-------|------------------------------|--------------------------------|
| **AMSI bypass** | AMSI docs + ATT&CK T1562.001 | API hooking, patch `AmsiScanBuffer`, script obfuscation — **write the Sigma rule you’d use to catch it** |
| **ETW patching** | ETW docs + T1562.006 | Provider tampering — correlate with kernel callbacks |
| **Unhooked ntdll** | Windows Internals + public RE posts | Direct syscalls vs hooked stubs — compare telemetry |
| **Signed binary proxy (LOLBAS)** | LOLBAS project | `mshta`, `regsvr32`, `rundll32` — process ancestry rules |
| **SmartScreen / MOTW** | https://learn.microsoft.com/en-us/windows/security/threat-protection/microsoft-defender-smartscreen/microsoft-defender-smartscreen-overview | Mark-of-the-Web, reputation |
| **Controlled Folder Access** | Defender ransomware protection docs | Test harness impact on file encryption samples |
| **ASR rules** | https://learn.microsoft.com/en-us/microsoft-365/security/defender-endpoint/attack-surface-reduction | Block Office macros, child process spawn, etc. |
| **Tamper Protection** | Defender tamper protection docs | What blocks service/registry tampering |

Public educational PoC repos (analyze in VM, then write detections):
- https://github.com/rasta-mouse/AmsiScanBufferBypass — classic AMSI research PoC
- https://github.com/S3cur3Th1sSh1t/Amsi-Bypass-Powershell — PowerShell AMSI variants
- https://github.com/bats3c/Ghost-In-The-Logs — ETW bypass research
- https://github.com/Offensive-Panda/Defence-Techniques — defensive technique catalog (ironic name, useful for blue)

---

## Quick search queries for Miku

```
rag_query "AMSI bypass detection sigma"
rag_query "Windows 11 HVCI exploit mitigation"
rag_query "CVE-2024" source_type=cve
malware_intel <sha256>
cve_lookup CVE-2024-XXXX
web_search "Microsoft Defender ASR rules 2025"
```

---

## Related skills

| Skill | When |
|-------|------|
| **`windows-rat-dev`** | **Win11 RAT / implant / C2 lab builds** |
| `malware-authoring` | Building technique demos + detection twins |
| `malware-analysis` | Analyst pass on your own builds |
| `windows-api` | Win32/NT API cards |
| `cve-research` / `cve-malware-test` | CVE intel + lab harness |
| `malware-intel` | MalwareBazaar → family cards |
| `knowledge-rag` | Index + search workflow |

---

## Windows RAT / C2 research (lab)

| Resource | URL | Notes |
|----------|-----|-------|
| **Skill: windows-rat-dev** | `skills/windows-rat-dev/SKILL.md` | Primary playbook — architecture, phases, Win11 constraints |
| **RAT architecture** | `workspace/malware-authoring/rat/architecture.md` | Modules, transport, loaders |
| **Sliver** | https://github.com/BishopFox/sliver | Reference C2 — diff against custom beacon |
| **Havoc** | https://github.com/HavocFramework/Havoc | Demon agent + BOF research |
| **Merlin** | https://github.com/Ne0nd0g/merlin | HTTP/2 agent |
| **PoshC2** | https://github.com/nettitude/PoshC2 | Staging patterns |
| **Donut / sRDI** | https://github.com/TheWover/donut · https://github.com/monoxgas/sRDI | Shellcode staging |
| **MITRE C2 / Persistence** | https://attack.mitre.org/tactics/TA0011/ · https://attack.mitre.org/tactics/TA0003/ | ATT&CK map every project |

Paths: binaries `labs/rat/win11/<name>/` · notes `workspace/malware-authoring/rat/projects/`
