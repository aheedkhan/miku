---
name: android-internals
description: Android / AOSP / NDK / Binder / SELinux / ART for development, security research, and Android malware context.
---

# Android internals

## When to use
APK/native debugging, JNI/NDK, Binder IPC, permissions, SELinux denials, AOSP builds, and grounding **Android malware** analysis/authoring in the real stack.

## Method
1. Clarify API level / device / eng vs user build.
2. Evidence: `adb`, logcat, `dumpsys`, tombstones; root only on lab images.
3. Map: app → Framework → Binder → native service → kernel (SELinux).
4. Reverse: jadx/apktool for DEX; Ghidra/r2 for `.so`.
5. Save lasting notes under `workspace/android/platform-notes/`.
6. For malware **build**, load `android-malware-dev`. For malware **analysis**, load `android-malware-analysis`.

## Teaching defaults
- IPC / lifecycle diagram before code.
- Call out exported components, PendingIntent, WebView, and SELinux early.
