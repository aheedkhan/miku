"""Android reverse-engineering/dynamic-analysis toolbelt: apktool decode/rebuild, jadx
decompile, zipalign+apksigner signing (correct modern order — zipalign BEFORE signing, not
the legacy jarsigner-then-align order), adb install/logcat/pull/push, frida process listing,
and objection patching.

Every action shutil.which()-checks its binary FIRST and returns a clear ToolResult.failure
naming what to install when it's missing — verified live in this environment, where NONE of
apktool/jadx/frida/objection/apksigner/zipalign are installed (only adb is).

fs-adjacent paths (apk_path/out_dir/src_dir/local) are resolved relative to Path.cwd() at
call time, never hardcoded to any particular repo — Hermes runs from inside whatever project
the user has cd'd into.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from hermes.config import HermesConfig
from hermes.tools.base import Tool, ToolResult, ToolSchema

_INSTALL_HINTS = {
    "apktool": "install apktool (https://apktool.org/ — e.g. `apt install apktool` or download the wrapper script)",
    "jadx": "install jadx (https://github.com/skylot/jadx/releases)",
    "zipalign": "install the Android SDK build-tools (zipalign ships with them; `apt install android-sdk-build-tools` or via `sdkmanager`)",
    "apksigner": "install the Android SDK build-tools (apksigner ships with them; `apt install android-sdk-build-tools` or via `sdkmanager`)",
    "adb": "install Android platform-tools (`apt install android-tools-adb` or download from https://developer.android.com/tools/releases/platform-tools)",
    "frida-ps": "install frida-tools (`pip install frida-tools`) — also requires frida-server running on the target device",
    "objection": "install objection (`pip install objection`)",
}


def _which_or_fail(binary: str) -> str | None:
    """Returns the resolved path, or None (caller should build a ToolResult.failure)."""
    return shutil.which(binary)


def _missing_binary_result(binary: str) -> ToolResult:
    hint = _INSTALL_HINTS.get(binary, f"install {binary} and ensure it's on PATH")
    return ToolResult.failure(
        f"missing_binary:{binary}",
        f"'{binary}' is not installed or not on PATH. To use this action, {hint}.",
    )


async def _run(cmd: list[str], *, cwd: Path | None = None, timeout: float = 300.0) -> tuple[int, str, str]:
    """Run a subprocess without a shell (argv list — no injection risk from path/arg content),
    capturing stdout/stderr, with a hard timeout so a hung external tool can't hang the agent."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return -1, "", f"Command timed out after {timeout}s: {' '.join(cmd)}"
    return proc.returncode or 0, stdout_b.decode(errors="replace"), stderr_b.decode(errors="replace")


def _result_from_run(rc: int, stdout: str, stderr: str, ok_message: str) -> ToolResult:
    output = (stdout + ("\n" + stderr if stderr.strip() else "")).strip()
    if rc != 0:
        return ToolResult.failure(f"exit_code_{rc}", output or f"Command exited {rc} with no output.")
    return ToolResult.success(output or ok_message)


async def _adb_device_connected(adb_bin: str, serial: str | None) -> str | None:
    """Fast (<=10s) pre-check for a live device/emulator. Real, live-verified behavior on
    this box: `adb logcat`/`install`/`pull`/`push` do NOT fail fast when no device is
    attached — they print "- waiting for device -" and block for the full subprocess
    timeout (confirmed: still blocked after 2+ minutes, only unblocked when killed). `adb
    devices` itself always returns immediately whether or not anything is attached, so
    checking it first is what actually prevents the hang. Returns None if a suitable device
    is present, else a human-readable error string."""
    rc, out, err = await _run([adb_bin, "devices"], timeout=10.0)
    if rc != 0:
        return f"'adb devices' failed: {(out + err).strip()}"
    device_lines = [
        line for line in out.splitlines()[1:]
        if line.strip() and "\t" in line and line.split("\t", 1)[1].strip() == "device"
    ]
    serials = [line.split("\t", 1)[0].strip() for line in device_lines]
    if not serials:
        return "No Android device/emulator connected (`adb devices` lists none). Plug in a device with USB debugging enabled, or start an emulator, then retry."
    if serial and serial not in serials:
        return f"Device serial '{serial}' not found among connected devices: {', '.join(serials)}."
    return None


def build_tools(config: HermesConfig) -> list[Tool]:
    async def android(
        action: str,
        apk_path: str | None = None,
        out_dir: str | None = None,
        src_dir: str | None = None,
        out_apk: str | None = None,
        keystore: str | None = None,
        keystore_pass: str | None = None,
        serial: str | None = None,
        remote: str | None = None,
        local: str | None = None,
        lines: int = 200,
    ) -> ToolResult:
        cwd = Path.cwd()

        def resolve(p: str) -> str:
            path = Path(p).expanduser()
            return str(path if path.is_absolute() else cwd / path)

        # -------- apktool --------
        if action == "decode_apk":
            if not apk_path or not out_dir:
                return ToolResult.failure("missing_argument", "decode_apk requires apk_path and out_dir.")
            binary = _which_or_fail("apktool")
            if not binary:
                return _missing_binary_result("apktool")
            rc, out, err = await _run([binary, "d", resolve(apk_path), "-o", resolve(out_dir)])
            return _result_from_run(rc, out, err, f"Decoded {apk_path} to {out_dir}.")

        if action == "rebuild_apk":
            if not src_dir or not out_apk:
                return ToolResult.failure("missing_argument", "rebuild_apk requires src_dir and out_apk.")
            binary = _which_or_fail("apktool")
            if not binary:
                return _missing_binary_result("apktool")
            rc, out, err = await _run([binary, "b", resolve(src_dir), "-o", resolve(out_apk)])
            return _result_from_run(rc, out, err, f"Rebuilt {src_dir} to {out_apk}.")

        # -------- jadx --------
        if action == "decompile_jadx":
            if not apk_path or not out_dir:
                return ToolResult.failure("missing_argument", "decompile_jadx requires apk_path and out_dir.")
            binary = _which_or_fail("jadx")
            if not binary:
                return _missing_binary_result("jadx")
            rc, out, err = await _run([binary, "-d", resolve(out_dir), resolve(apk_path)])
            return _result_from_run(rc, out, err, f"Decompiled {apk_path} to {out_dir}.")

        # -------- signing: zipalign THEN apksigner (correct modern order) --------
        if action == "sign_apk":
            if not apk_path or not keystore or not keystore_pass:
                return ToolResult.failure(
                    "missing_argument", "sign_apk requires apk_path, keystore, and keystore_pass."
                )
            zipalign_bin = _which_or_fail("zipalign")
            if not zipalign_bin:
                return _missing_binary_result("zipalign")
            apksigner_bin = _which_or_fail("apksigner")
            if not apksigner_bin:
                return _missing_binary_result("apksigner")

            resolved_apk = resolve(apk_path)
            final_out = resolve(out_apk) if out_apk else str(Path(resolved_apk).with_suffix(".aligned-signed.apk"))
            aligned_tmp = str(Path(final_out).with_suffix(".tmp-aligned.apk"))

            rc, out, err = await _run([zipalign_bin, "-v", "4", resolved_apk, aligned_tmp])
            if rc != 0:
                return _result_from_run(rc, out, err, "")

            rc2, out2, err2 = await _run(
                [
                    apksigner_bin, "sign",
                    "--ks", resolve(keystore),
                    "--ks-pass", f"pass:{keystore_pass}",
                    "--out", final_out,
                    aligned_tmp,
                ]
            )
            Path(aligned_tmp).unlink(missing_ok=True)
            if rc2 != 0:
                return _result_from_run(rc2, out2, err2, "")
            combined = (out + "\n" + out2).strip()
            return ToolResult.success(combined or f"Zipaligned and signed -> {final_out}", display=f"Signed APK written to {final_out}")

        # -------- adb --------
        if action == "adb_install":
            if not apk_path:
                return ToolResult.failure("missing_argument", "adb_install requires apk_path.")
            binary = _which_or_fail("adb")
            if not binary:
                return _missing_binary_result("adb")
            device_err = await _adb_device_connected(binary, serial)
            if device_err:
                return ToolResult.failure("no_device", device_err)
            cmd = [binary] + (["-s", serial] if serial else []) + ["install", "-r", resolve(apk_path)]
            rc, out, err = await _run(cmd, timeout=120.0)
            return _result_from_run(rc, out, err, f"Installed {apk_path}.")

        if action == "adb_logcat":
            binary = _which_or_fail("adb")
            if not binary:
                return _missing_binary_result("adb")
            device_err = await _adb_device_connected(binary, serial)
            if device_err:
                return ToolResult.failure("no_device", device_err)
            cmd = [binary] + (["-s", serial] if serial else []) + ["logcat", "-d", "-t", str(int(lines))]
            rc, out, err = await _run(cmd, timeout=30.0)
            return _result_from_run(rc, out, err, "No logcat output.")

        if action == "adb_pull":
            if not remote or not local:
                return ToolResult.failure("missing_argument", "adb_pull requires remote and local.")
            binary = _which_or_fail("adb")
            if not binary:
                return _missing_binary_result("adb")
            device_err = await _adb_device_connected(binary, serial)
            if device_err:
                return ToolResult.failure("no_device", device_err)
            cmd = [binary] + (["-s", serial] if serial else []) + ["pull", remote, resolve(local)]
            rc, out, err = await _run(cmd)
            return _result_from_run(rc, out, err, f"Pulled {remote} to {local}.")

        if action == "adb_push":
            if not remote or not local:
                return ToolResult.failure("missing_argument", "adb_push requires remote and local.")
            binary = _which_or_fail("adb")
            if not binary:
                return _missing_binary_result("adb")
            device_err = await _adb_device_connected(binary, serial)
            if device_err:
                return ToolResult.failure("no_device", device_err)
            cmd = [binary] + (["-s", serial] if serial else []) + ["push", resolve(local), remote]
            rc, out, err = await _run(cmd)
            return _result_from_run(rc, out, err, f"Pushed {local} to {remote}.")

        # -------- frida / objection --------
        if action == "frida_list_processes":
            binary = _which_or_fail("frida-ps")
            if not binary:
                return _missing_binary_result("frida-ps")
            cmd = [binary, "-Uai"]
            rc, out, err = await _run(cmd, timeout=30.0)
            return _result_from_run(rc, out, err, "No processes listed.")

        if action == "objection_patch":
            if not apk_path:
                return ToolResult.failure("missing_argument", "objection_patch requires apk_path.")
            binary = _which_or_fail("objection")
            if not binary:
                return _missing_binary_result("objection")
            cmd = [binary, "patchapk", "-s", resolve(apk_path)]
            rc, out, err = await _run(cmd, timeout=600.0)
            return _result_from_run(rc, out, err, f"Patched {apk_path}.")

        return ToolResult.failure(
            "bad_action",
            f"Unknown action '{action}'. Valid actions: decode_apk, rebuild_apk, decompile_jadx, "
            "sign_apk, adb_install, adb_logcat, adb_pull, adb_push, frida_list_processes, objection_patch.",
        )

    schema = ToolSchema(
        name="android",
        description=(
            "Android APK reverse-engineering and device toolbelt: decode/rebuild with apktool, "
            "decompile with jadx, zipalign+sign an APK with apksigner (correct order: align "
            "before signing), adb install/logcat/pull/push, list processes with frida, or patch "
            "an APK with objection. Every action checks its required binary is installed first "
            "and fails clearly (naming what to install) if not — none of apktool/jadx/frida/"
            "objection/apksigner/zipalign ship with Hermes itself."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "decode_apk", "rebuild_apk", "decompile_jadx", "sign_apk",
                        "adb_install", "adb_logcat", "adb_pull", "adb_push",
                        "frida_list_processes", "objection_patch",
                    ],
                },
                "apk_path": {"type": "string", "description": "Path to an .apk (relative to cwd or absolute)."},
                "out_dir": {"type": "string", "description": "Output directory for decode_apk/decompile_jadx."},
                "src_dir": {"type": "string", "description": "Decoded apktool project directory, for rebuild_apk."},
                "out_apk": {"type": "string", "description": "Output .apk path for rebuild_apk/sign_apk."},
                "keystore": {"type": "string", "description": "Path to a Java keystore (.jks/.keystore) for sign_apk."},
                "keystore_pass": {"type": "string", "description": "Keystore password for sign_apk."},
                "serial": {"type": "string", "description": "Optional adb/frida device serial (adb -s / frida -U targets one device already; pass to disambiguate multiple)."},
                "remote": {"type": "string", "description": "Device-side path, for adb_pull (source) / adb_push (destination)."},
                "local": {"type": "string", "description": "Host-side path, for adb_pull (destination) / adb_push (source)."},
                "lines": {"type": "integer", "description": "Number of trailing logcat lines to dump (adb_logcat). Default 200."},
            },
            "required": ["action"],
        },
    )
    return [Tool(schema=schema, handler=android)]
