# Building for Xbox 360

## Prerequisites

Use Windows with PowerShell, Git for Windows, Python, CMake, and Visual Studio
2022 C++ host tools. Native compilation also requires an installed Xbox 360 SDK
and its MSBuild/toolset integration (`2010-01`). Host tests that compile C++ use
the Visual Studio x86 tools. Supply your own supported US Super Smash Bros. ROM;
the extraction script validates and normalizes its byte order.

Obtain [Shipyard](https://github.com/becaring/Shipyard) and check out the exact
revision in `platform-base.lock.json`. Point `XBOX360_PLATFORM_BASE` at that
checkout if the lock's relative location does not match your layout:

```powershell
$env:XBOX360_PLATFORM_BASE = (Resolve-Path ../Shipyard).Path
python -B tools/platform_base.py
```

Verification checks the commit, API, and baseline manifest. A location override
does not override the required revision. `XEDK` may select an SDK installation;
otherwise the build script uses its default Microsoft Xbox 360 SDK directory.

## Acquire and build

Run from the Warwing repository root:

```powershell
./tools/fetch-sources.ps1
./tools/fetch-dependencies.ps1
./tools/setup-host-deps.ps1
./tools/build-assets.ps1 -Rom './Super Smash Bros. (USA).n64'
./platform/xbox360/build.ps1 -Regenerate -Rebuild
```

Source acquisition selects BattleShip and its exact submodule revisions.
Dependency acquisition follows `dependencies.lock.json`. Existing checkouts can
be checked with `./tools/fetch-dependencies.ps1 -VerifyOnly`; local source edits
must be resolved rather than overwritten by acquisition scripts.

Asset preparation builds the selected Torch on the host and extracts the real
`BattleShip.o2r` and `f3d.o2r` inputs. `-Regenerate` runs the maintained projection
owners, then stages physical compiler inputs and generated native projects.
`-Rebuild` requests fresh native compilation. Routine builds can omit those
flags when their inputs have not changed.

The application output is
`scratch/application-xdk/native/build/Smash360.xex`, alongside its required
archives. Native build logs and compile/link receipts remain under
`scratch/application-xdk/native`. The build checks scheduler/VI/message symbol
ownership, PPC logger control flow, and RDP initialization.

## Targeted work and diagnostics

`build.ps1 -PrepareOnly` stages and verifies the application without compilation.
`-CompileOnly` accepts a selected production source path; use the generated
`project-items.json` to identify that path. The standalone port audit accepts,
for example, `python -B tools/prepare_port_xdk.py --source port/port_dl_ranges.cpp`.
Its generated dependencies must already be prepared.

Normal builds compile full-profiler scopes out. Use `build.ps1 -FullProfiling`
only for a diagnostic build; see [profiling](../platform/xbox360/runtime/PROFILING.md).
The optional `game:\smash360.env` file is loaded once before workers start.
Its absence preserves normal defaults; see
[environment lookup](../platform/xbox360/ENVIRONMENT.md).

If generated output needs clearing, inspect
`python -B tools/empty-owned-generated.py --list` before using `--clean`.
That utility preserves previous XEX receipts and removes only its named owned
outputs. Keep ROMs, extracted archives, SDK files, build outputs, caches, and
local diagnostic packages outside source control.
