---
name: lab-build
description: >-
  Compile and package labs — make/ninja/cmake, mingw, cargo, Gradle, Python.
  Use when building, fixing compile errors, or setting Debug/ASAN flags before
  test/debug.
---

# Lab build (compile)

## Goal
**Configure → compile → smoke-test** with a repeatable command line. On failure: fix the *first* error, don't thrash flags.

## When to use
- "Build / compile / link this"
- Labs under `labs/` (RAT implants, CVE harnesses, Android samples)
- Cross-compile (e.g. `x86_64-w64-mingw32-gcc` for Win11 lab binaries on Linux/WSL)

## Workflow
1. Detect build system: `CMakeLists.txt`, `Makefile`, `meson.build`, `Cargo.toml`, `build.gradle`, `pyproject.toml`
2. Read README / existing scripts **before** inventing flags
3. Out-of-tree builds when possible (`build/`, `out/`)
4. Prefer **Debug + symbols** for lab work (`-g`, `CMAKE_BUILD_TYPE=Debug`)
5. Compile; on error → see **Compile errors** below
6. Smoke-test (`--help`, unit test, one happy path)
7. On runtime failure → `test-harness` then `debug-triage` / `debugger`

## Compile errors (discipline)
1. Scroll to the **first** error — ignore cascade noise
2. Classify: missing header/lib | syntax | type | link undefined ref | wrong target triple
3. Fix minimal cause; rebuild
4. If include/lib path hell: print the actual compile line (`make VERBOSE=1`, `ninja -v`, `cargo build -v`)

| Error shape | Likely fix |
|-------------|------------|
| `No such file or directory: foo.h` | package/`-I` path / wrong include |
| `undefined reference to X` | missing `-l` / object not in link |
| `cannot find -lfoo` | install `-dev` package or `-L` |
| mingw `WinMain` / subsystem | `-mconsole` / correct entry |
| Android Gradle SDK missing | `local.properties` / `sdkmanager` |

## Defaults by stack
| Stack | Prefer |
|-------|--------|
| C/C++ Linux | CMake + Ninja, `-g -O0`, optional `-fsanitize=address,undefined` |
| C Windows cross | `x86_64-w64-mingw32-gcc`, static winpthreads if needed |
| Rust | `cargo build` / `cargo test`; `RUSTFLAGS=-g` |
| Android app | `./gradlew assembleDebug` |
| Python | venv + `pip install -e .` |

## ASAN quick rebuild (C/C++)
```bash
cmake -B build -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_C_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer" \
  -DCMAKE_CXX_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer" \
  -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=address,undefined"
cmake --build build
```

## Record
Save exact build commands in the lab note. Never commit `out/` / huge artifacts.

## Hand-offs
- Crash after successful build → `debugger` / `debug-triage`
- Need a failing check → `test-harness`
- Android toolchain missing → `env-bootstrap` + `docs/android-workflow.md`

## Never
- `make clean` / disk wipes without confirming
- Ship stripped Release as the only lab binary when you still need stacks
