# Building

## Prerequisites and layout

Use Windows, PowerShell, Git, Python, CMake, Visual Studio 2022 C++ host tools,
and an installed Xbox 360 SDK with its `2010-01` MSBuild integration. Host C++
tests use the Visual Studio x86 tools. `XEDK` can select the SDK installation.

Clone Shipyard as a sibling of the game repository. `platform-base.lock.json`
uses `../Shipyard`; check out its exact revision. For a different location, set:

```powershell
$env:XBOX360_PLATFORM_BASE = 'D:/path/to/Shipyard'
python -B tools/platform_base.py
```

The override changes the location, while revision, API, and baseline checks
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

Source acquisition uses pinned BattleShip submodules. Dependencies follow
`dependencies.lock.json`; `fetch-dependencies.ps1 -VerifyOnly` checks a checkout.
See [Assets](ASSETS.md) for extraction and packaging.

The executable is `scratch/application-xdk/native/build/Smash360.xex`.
`-Regenerate` projects sources and stages native projects; `-Rebuild` recompiles.
Omit these flags when the corresponding inputs are unchanged. Logs and build
records stay under `scratch/application-xdk/native`.

Before `platform/xbox360/package.ps1`, `python -B tools/build_shader_pack.py --jobs 8`
can build the prebuilt shader pack from the regenerated projections with the XDK's
`fxc.exe`; packaging copies it beside the XEX. The XEX verifies each packed program
against its own shader generator on first use and compiles any mismatch itself.

`build.ps1 -PrepareOnly` stages without compiling. `-CompileOnly` accepts a
production source path from `project-items.json`. A port source can also be
audited with `python -B tools/prepare_port_xdk.py --source port/port_dl_ranges.cpp`
after preparing its dependencies.

## Contributor checks

Edit maintained projectors or adapters and regenerate their outputs. Keep game
behavior in Warwing and reusable Xbox services in Shipyard. Preserve source
locks, legal notices, source mappings, and ordering contracts. Generated output
is not an edit location. A partial symbol index cannot establish absence of callers.

```powershell
python -B tools/test_host_ci.py
```

CI runs the hygiene guard and portable tests. The focused suites under `tests/`
also include C++ contracts and XDK probes; use their runner's prerequisites.
`tools/check_projector_style.py` checks the 140-character prepare-script limit.
After runtime changes, build the affected Xbox integration and test it on hardware.

Normal builds omit full-profiler scopes. `build.ps1 -FullProfiling` enables them;
`SMASH360_PROFILE=0` disables reporting and `SMASH360_PROFILE_DETAIL=1` opts into
detail in that build. Packaging flags `-ProfileDisabled` and `-ProfileDetail`
are mutually exclusive. See [Architecture](ARCHITECTURE.md) for timing semantics.
The optional `game:\smash360.env` is loaded before workers start.

Inspect `python -B tools/empty-owned-generated.py --list` before using `--clean`.
It removes named generated outputs and preserves previous executable build records.
Keep local measurements, logs, assets, SDK files, and packages in ignored storage.
