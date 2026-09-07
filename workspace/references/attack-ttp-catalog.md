# ATT&CK / TTP catalog (lab quick-reference)

Authorized research / owned VMs only. Use with skill `attack-ttps`.
Prefer **one row → one lab demo** under `labs/techniques/`.

Official browser: https://attack.mitre.org/ — fetch when IDs need confirming.

## How Miku uses this

1. Pick rows that match the user's objective
2. Implement mechanism column (minimal)
3. Prove success criteria
4. Write detection twin
5. Save notes under `workspace/malware-authoring/techniques/`

---

## Execution

| ID | Name | Mechanism (Win / notes) | Lab proof | Detection twin starters |
|----|------|-------------------------|-----------|-------------------------|
| T1059.001 | PowerShell | `powershell.exe -enc` / AMSI-visible scripts | Process tree shows powershell child | ScriptBlock logging, AMSI events |
| T1059.003 | Windows Command Shell | `cmd.exe /c`, `CreateProcess` | cmd child of implant | Sysmon 1 parent/child |
| T1059.005 | Visual Basic | `.vbs` / wscript | wscript in tree | Script host + file create |
| T1204.002 | User Execution: Malicious File | Lab dropper double-click / shared folder | User launches sample | Mark-of-web, SmartScreen |

## Persistence

| ID | Name | Mechanism | Lab proof | Detection twin starters |
|----|------|-----------|-----------|-------------------------|
| T1547.001 | Registry Run Keys | `HKCU\...\Run` value → implant path | Survives logoff/logon (snapshot) | Sysmon 13, Autoruns |
| T1053.005 | Scheduled Task | `schtasks` / Task Scheduler COM | Task runs at logon/interval | Sysmon 1 from taskeng, 4698 |
| T1543.003 | Windows Service | `CreateService` / sc.exe | Service start → implant | Service install events |
| T1546.003 | WMI Event Subscription | permanent event consumer (advanced) | Trigger fires after reboot | WMI activity / Sysmon 19–21 |

## Defense evasion (separate phase only)

| ID | Name | Mechanism | Lab proof | Detection twin starters |
|----|------|-----------|-----------|-------------------------|
| T1562.001 | Disable or Modify Tools | Defender preference APIs (often blocked by Tamper Protect) | Preference change attempt logged | Tamper Protection, 5001 |
| T1562.001 | AMSI bypass research | Patch `amsi.dll` / provider (lab) | AMSI fail-open on test script | AMSI provider unload / memory integrity |
| T1562.006 | Indicator Blocking (ETW) | Patch / blind ETW providers | Provider silence in trace | ETW Threat-Intelligence gaps |
| T1027 | Obfuscated Files | pack / encrypt strings (after clear version works) | Strings less obvious | Entropy, unpack YARA |
| T1055 | Process Injection | See `win32-injection-map.md` | Code runs in remote PID | Sysmon 8/10, RWX remote |
| T1218 | System Binary Proxy | rundll32 / regsvr32 / mshta LOLBAS | Proxy hosts payload | LOLBAS parent-child |

## Discovery

| ID | Name | Mechanism | Lab proof | Detection twin starters |
|----|------|-----------|-----------|-------------------------|
| T1082 | System Information Discovery | `GetComputerName`, `RtlGetVersion` | Beacon metadata fields | Unusual API spam (weak alone) |
| T1057 | Process Discovery | Toolhelp32 / NtQuerySystemInformation | Process list in C2 | Process enumeration telemetry |
| T1083 | File & Directory Discovery | FindFirstFile / walk dirs | Listing returned | Volume scan patterns |
| T1016 | System Network Config | `GetAdaptersInfo`, ipconfig spawn | IP/DNS in check-in | Discovery burst after exec |

## Collection (module labs)

| ID | Name | Mechanism | Lab proof | Detection twin starters |
|----|------|-----------|-----------|-------------------------|
| T1113 | Screen Capture | GDI / Desktop Duplication API | PNG/JPEG artifact | Desktop capture API + net |
| T1005 | Data from Local System | Read targeted paths | File contents exfil | Sensitive path read + C2 |
| T1115 | Clipboard Data | `OpenClipboard` / CF_UNICODETEXT | Clipboard text in C2 | Clipboard API hooks |

## Command and control

| ID | Name | Mechanism | Lab proof | Detection twin starters |
|----|------|-----------|-----------|-------------------------|
| T1071.001 | Web Protocols | WinHTTP/WinInet HTTPS POST beacon | Check-in on lab C2 | Unusual POST from non-browser |
| T1071.004 | DNS | DNS TXT/null C2 (advanced) | Resolver queries to lab DNS | High entropy DNS |
| T1095 | Non-Application Layer | raw TCP/UDP sockets | Socket to C2 IP:port | Non-std ports from implant |
| T1029 | Scheduled Transfer | sleep + jitter | Irregular beacon intervals | Beaconing analytics |
| T1573 | Encrypted Channel | TLS / custom crypto | Encrypted body | JA3 / cert pinning lab notes |

## Credential access (lab caution)

| ID | Name | Mechanism | Lab proof | Detection twin starters |
|----|------|-----------|-----------|-------------------------|
| T1003.001 | LSASS Memory | MiniDump / read (Credential Guard may block) | Dump file on lab VM only | Sysmon 10 to lsass |
| T1056.001 | Keylogging | WH_KEYBOARD_LL / raw input | Key buffer in module test | Hook install telemetry |

Document Credential Guard / HVCI state every run. Prefer **fake lab secrets** over real passwords.

## Lateral movement / impact

Default **non-goals** for research RATs unless user explicitly expands scope.
If needed: study only inside multi-VM lab VLAN; never against third parties.

---

## Android quick map (pair `android-malware-*`)

| Area | Example techniques | Notes |
|------|-------------------|-------|
| Persistence | receivers, jobs, accessibility abuse | Document OEM differences |
| C2 | HTTPS / FCM mis-use research | Lab server only |
| Collection | SMS, contacts, accessibility | Explicit consent in lab APK notes |
| Evasion | packers, anti-emulation | After clear APK works |

## Linux quick map (pair `linux-internals`)

| ID-ish behavior | Mechanism | Detection |
|-----------------|-----------|-----------|
| Persistence | cron, systemd user unit, `.bashrc` | unit file integrity |
| C2 | HTTPS / raw socket | unexpected egress |
| Injection / hooks | `LD_PRELOAD`, ptrace | preload env, ptrace denials |

---

## Lab path convention

```
labs/techniques/win11/T1547.001-run-key/
labs/techniques/win11/T1055-injection/
labs/techniques/android/...
workspace/malware-authoring/techniques/T1547.001-run-key.md
```
