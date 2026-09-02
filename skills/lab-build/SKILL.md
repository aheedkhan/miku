---
name: lab-build
description: >-
  General project builds — make/ninja/cmake/meson, Gradle/Bazel, cargo, Python
  packaging, local services. Use for building labs, tools, backends, or any
  non-AOSP tree. For FYP AOSP sync/lunch/cf.sh use fyp-aosp-build instead.
---

# Lab build (general)

## Goal
Get a clean, repeatable build: configure → compile → smoke-test → record how.

## When to use
- "Build this" / "compile" / "make it run" outside the AOSP tree
- Labs under `labs/`, backends, Python/C/Rust tools, Podman stacks
- Reproducing a teammate's or prior-session build

## AOSP exception
If cwd / topic is FYP AOSP → use **`fyp-aosp-build`** (tag, lunch, `vsoc_x86_64_only/`, `cf.sh` only).

## Workflow
1. Detect build system (`CMakeLists.txt`, `meson.build`, `Makefile`, `build.gradle`, `Cargo.toml`, `pyproject.toml`, `Containerfile`)
2. Read README / existing scripts before inventing flags
3. Out-of-tree / isolated build dirs when possible (`build/`, `out/`)
4. Record exact commands in the lab note or report
5. Smoke-test one binary or endpoint; capture version/`--help` or a health check
6. On failure: jump to **`debug-triage`** (don't thrash random flags)

## Defaults
| Stack | Prefer |
|-------|--------|
| C/C++ | CMake + Ninja, Debug+ASAN for labs |
| Rust | `cargo build` / `cargo test` |
| Android app (not AOSP) | Gradle wrapper `./gradlew` |
| Python | venv + `pip install -e .` or uv |
| Services | Podman Compose over Docker when on this Fedora host |

## Long-term habits
- Pin toolchain / container digests in notes when reproducibility matters
- Never commit huge `out/` trees or secrets
- Prefer scripts in-repo (`scripts/`, `cf.sh`-style wrappers) over tribal memory

## Never
- `launch_cvd` bare for FYP — that's `cf.sh`
- Run destructive `clean` / disk wipes without confirming with the user
