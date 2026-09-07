# Android RE toolchain — quick reference

Authorized lab use only. Pair with skill `android-malware-analysis` / `android-malware-dev`.

## Pipeline order (always)

1. `apktool d app.apk` — decode smali + resources (editable)
2. `jadx app.apk` — readable Java reference (do not edit jadx output)
3. Edit smali/resources under the apktool tree
4. `apktool b app-decoded/` → unsigned APK in `dist/`
5. `zipalign -p 4 in.apk out-aligned.apk` — **before** signing
6. `apksigner sign --ks lab.keystore out-aligned.apk`
7. `adb install -r` on lab emulator/device
8. Frida / objection for runtime hooks

Wrong order (sign then zipalign with apksigner v2/v3) invalidates the signature.

## Tool map

| Tool | Role |
|------|------|
| apktool | decode / rebuild |
| jadx | decompile to Java |
| zipalign / apksigner | align then sign (SDK build-tools) |
| adb | install, logcat, pull/push |
| frida-tools + frida-server | hooks on device |
| objection | common mobile bypass one-liners |

## Static triage checklist

- Record SHA256 before install
- `aapt dump badging` / package + permissions
- Multi-DEX, assets, native `.so` (ABI)
- Packer / obfuscation hints (PIE, DexGuard-class)
- Network endpoints in strings / smali

## Dynamic triage checklist

- Cold install on disposable AVD
- logcat from t+0 install → first activity → persistence → C2
- Accessibility / overlay / install-unknowns abuse
- Frida: list processes, hook crypto / pinning / root checks

## Lab hygiene

- Never commit APKs or samples to git — hash + notes only
- Detonate only on isolated emulator/VM
