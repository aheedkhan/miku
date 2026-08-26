# Android RE / malware-analysis workflow

`hermes/tools/android_tool.py` wraps the standard Android reverse-engineering toolchain as a
single Hermes tool — one flat tool with an `action` enum parameter (decode/decompile/rebuild/
align/sign/install/instrument) rather than one tool per step, per Hermes' tool-design
convention of grouping related operations on a shared resource. This document explains the
workflow it wraps, the order that actually matters, and exactly what you need to install for
each step to work.

None of these tools talk to each other automatically — Hermes' job is to drive each step and
carry state (the working directory, the current APK path, whether it's been resigned yet)
between them so you don't have to remember the invocation flags each time.

## The pipeline

```
   APK in hand
       │
       ▼
 1. apktool d app.apk         decode → smali + resources you can read/edit
       │
       ▼
 2. jadx app.apk              decompile → readable-ish Java, for understanding logic
       │                      (jadx output is read-only reference; you edit the apktool
       │                       smali/resources tree, not jadx's output)
       ▼
 3. (edit smali/resources)    patch logic, disable cert pinning, add logging, etc.
       │
       ▼
 4. apktool b app-decoded/    rebuild → app-decoded/dist/app.apk (unsigned, unaligned)
       │
       ▼
 5. zipalign -p 4 in.apk out-aligned.apk       ← align BEFORE signing
       │
       ▼
 6. apksigner sign --ks my.keystore out-aligned.apk   ← sign AFTER aligning
       │
       ▼
 7. adb install -r out-aligned.apk
       │
       ▼
 8. frida / objection          attach at runtime — hook methods, bypass checks,
                                dump memory, trace calls, live-patch behavior
```

### The one order people get backwards: zipalign, *then* sign

With the modern `apksigner` (APK Signature Scheme v2/v3), **zipalign must run before signing,
not after**. This is the opposite of the old `jarsigner`-era workflow, where you signed first
and zipalign didn't care because v1-only (JAR) signatures don't cover the zip alignment/padding
metadata.

`apksigner`'s v2/v3 signatures, by contrast, cover the entire APK file including its zip
structure. Run zipalign *after* signing with apksigner and you invalidate the signature you
just applied — the APK will fail Play Protect / PackageManager signature verification, or
`adb install` will reject it outright, and the confusing part is that `apksigner` itself won't
warn you at sign time — it's silently signing a file you're about to corrupt with realignment.

Correct order, always: **decode → edit → rebuild → zipalign → apksigner sign → install.**

## What each binary is and where it comes from

| Tool | Purpose | Install from |
|---|---|---|
| `apktool` | decode APK → smali/resources, rebuild back to APK | [github.com/iBotPeaches/Apktool](https://github.com/iBotPeaches/Apktool) releases, or your distro's package manager (e.g. `sudo dnf install apktool` on Fedora, `sudo apt install apktool` on Debian/Ubuntu) |
| `jadx` | decompile APK/dex → Java source for reading | [github.com/skylot/jadx](https://github.com/skylot/jadx) releases (ships `jadx` and `jadx-gui`) |
| `zipalign` | align zip entries for mmap-friendly APKs | Android SDK **build-tools** (`build-tools/<version>/zipalign`), via Android Studio's SDK Manager or `sdkmanager "build-tools;<version>"` |
| `apksigner` | sign APKs with v2/v3 signature schemes | Android SDK **build-tools** (`build-tools/<version>/apksigner`) — same package as zipalign |
| `adb` | install/uninstall, logcat, port-forward to device/emulator | Android SDK **platform-tools**, or your distro's package (e.g. Fedora's `android-tools` package — this is the one already on this box) |
| `frida` / `frida-server` | dynamic instrumentation: hook Java/native methods at runtime | `pip install frida-tools` on the host (gives you the `frida` CLI/Python bindings) **plus** a matching-version `frida-server` binary pushed to the device/emulator at `/data/local/tmp/frida-server` (download from [github.com/frida/frida/releases](https://github.com/frida/frida/releases) — must match your `frida-tools` version and the device's ABI) |
| `objection` | frida-powered runtime toolkit: cert-pinning bypass, root-detection bypass, memory dump, one-liners for common mobile pentest tasks | `pip install objection` (uses `frida` under the hood, so both need matching versions) |

`apktool`, `jadx`, `zipalign`/`apksigner`, and `adb` are all standalone binaries/JARs —
`android_tool.py` probes each with `shutil.which()` before attempting to use it, and any action
that needs a missing binary fails with a clear `ToolResult.failure(...)` naming exactly what to
install and from where, rather than crashing or hanging. `frida`/`objection` are Python packages
installed into the same venv Hermes runs in (`pip install frida-tools objection` inside
`.venv`), checked with `importlib.util.find_spec` rather than `which`.

### What's actually installed on this dev box, checked live with `shutil.which()`

```
apktool      -> NOT FOUND
jadx         -> NOT FOUND
frida        -> NOT FOUND
frida-server -> NOT FOUND
objection    -> NOT FOUND
apksigner    -> NOT FOUND
zipalign     -> NOT FOUND
adb          -> /usr/bin/adb   (Fedora android-tools package, ADB 1.0.41 / 37.0.0)
```

So today, only `adb` is present. Everything else needs installing before `android_tool.py`'s
corresponding actions light up — expect its capability probe to report most actions
unavailable with install pointers until you set up the SDK build-tools, apktool, jadx, and the
frida/objection pip packages.

## Scheduling the daily CVE/project refresh

Hermes' daily refresh (CVE deltas + tracked `projects:` re-embedding) is designed to run
unattended on a schedule rather than only on demand from inside the REPL. `hermes/rag/daily_refresh.py`
is being built alongside this doc — at time of writing it doesn't exist in the tree yet, so the
exact entrypoint (module-level `if __name__ == "__main__":` guard, a `main()` function, or a
console-script entry in `pyproject.toml`) isn't confirmed here. Whichever it ends up being, the
scheduling side looks the same:

### Option A — cron

```bash
crontab -e
```

Add a line (adjust the repo path; `.venv/bin/python3` guarantees you're using Hermes' own venv
and its installed dependencies, not the system Python):

```cron
0 6 * * * /path/to/miku/.venv/bin/python3 -m hermes.rag.daily_refresh
```

### Option B — systemd user timer

`~/.config/systemd/user/hermes-refresh.service`:

```ini
[Unit]
Description=Hermes daily CVE/project refresh

[Service]
Type=oneshot
ExecStart=/path/to/miku/.venv/bin/python3 -m hermes.rag.daily_refresh
```

`~/.config/systemd/user/hermes-refresh.timer`:

```ini
[Unit]
Description=Run Hermes daily refresh once a day

[Timer]
OnCalendar=06:00
Persistent=true

[Install]
WantedBy=timers.target
```

Then:

```bash
systemctl --user daemon-reload
systemctl --user enable --now hermes-refresh.timer
```

**Integration note:** both options above assume `python3 -m hermes.rag.daily_refresh` runs the
refresh directly. If `daily_refresh.py` lands without a `if __name__ == "__main__":` guard (e.g.
it only exposes an async function meant to be called from the CLI), add one during integration:

```python
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())  # or whatever the real entrypoint function ends up being named
```

Confirm the actual entrypoint against the finished file before relying on either schedule above.
