# Building

## Prerequisites and layout

You need Windows, PowerShell, Git, Python, CMake, the Visual Studio 2022 C++
host tools, and an installed Xbox 360 SDK with its `2010-01` MSBuild
integration. Host C++ tests use the Visual Studio x86 tools. `XEDK` can select
the SDK installation.

Clone Shipyard next to the game repository. `platform-base.lock.json` points to
`../Shipyard`; check out the exact revision it names. To use another location, set:

```powershell
$env:XBOX360_PLATFORM_BASE = 'D:/path/to/Shipyard'
python -B tools/platform_base.py
```

The override changes only the location. The revision, API, and baseline checks
still apply.

## Build commands

Run from the repository root:

```powershell
./tools/fetch-sources.ps1
./tools/fetch-dependencies.ps1
./tools/setup-host-deps.ps1
./tools/build-assets.ps1 -Rom './Super Smash Bros. (USA).n64'
./platform/xbox360/build.ps1 -Regenerate -Rebuild
```

Sources come from the pinned BattleShip submodules. Dependencies follow
`dependencies.lock.json`; `fetch-dependencies.ps1 -VerifyOnly` checks a checkout.
[Assets](ASSETS.md) covers extraction and packaging.

The executable is `scratch/application-xdk/native/build/Smash360.xex`.
`-Regenerate` projects sources and stages native projects; `-Rebuild` recompiles.
Leave these flags off when the inputs have not changed. Logs and build records
stay under `scratch/application-xdk/native`.

Before `platform/xbox360/package.ps1`, you can run
`python -B tools/build_shader_pack.py --jobs 8` to build the prebuilt shader pack
from the regenerated projections with the XDK's `fxc.exe`. Packaging copies the
pack beside the XEX. On first use the XEX checks each packed program against its
own shader generator and compiles any mismatch itself. Programs compiled at run
time are cached in `smashsave:\smash360-shaders.cache`.

`build.ps1 -PrepareOnly` stages without compiling. `-CompileOnly` takes a
production source path from `project-items.json`. To audit a port source, prepare
its dependencies and run
`python -B tools/prepare_port_xdk.py --source port/port_dl_ranges.cpp`.

## Contributor checks

Edit the maintained projectors or adapters and regenerate their outputs. Game
behavior belongs in Warwing and reusable Xbox services in Shipyard. Keep source
locks, legal notices, source mappings, and ordering contracts intact. Generated
output is not a place to edit. A partial symbol index cannot show that a symbol
has no callers.

```powershell
python -B tools/test_host_ci.py
```

CI runs the hygiene guard and the portable tests. The focused suites under
`tests/` also hold C++ contracts and XDK probes; use their runner's
prerequisites. `tools/check_projector_style.py` checks the 140-character
prepare-script limit. After runtime changes, build the affected Xbox integration
and test it on hardware.

Normal builds omit full-profiler scopes. `build.ps1 -FullProfiling` enables them.
`SMASH360_PROFILE=0` disables reporting, and in that build
`SMASH360_PROFILE_DETAIL=1` turns on detail. The packaging flags
`-ProfileDisabled` and `-ProfileDetail` are mutually exclusive.
`platform/xbox360/package.ps1` writes the package's `smash360.env`, and its
`-TriangleTrace` and `-CommandTrace` switches enable triangle and command
tracing. The runtime loads the optional `game:\smash360.env` before workers
start. [Architecture](ARCHITECTURE.md) explains the timing semantics.

Run `python -B tools/empty-owned-generated.py --list` before using `--clean`.
`--clean` removes the named generated outputs and keeps previous executable
build records. Keep local measurements, logs, assets, SDK files, and packages in
ignored storage.
