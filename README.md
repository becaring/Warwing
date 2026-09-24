# Smash360 Xbox build

This repository holds the Smash360 Xbox adapters, generators, tests, and lock
files. `upstream/`, `scratch/`, `dist/`, the generated Visual Studio projects,
and user-supplied ROMs are deliberately outside its Git checkpoint. The
BattleShip and dependency revisions are pinned by `tools/fetch-sources.ps1`,
`tools/audit_sources.py`, and `dependencies.lock.json`. Shipyard is a separate
checkout selected by `platform-base.lock.json`.

On Windows with Git, Python, CMake/Visual Studio 2022, and Xbox 360 SDK 21256.3,
place Shipyard alongside this checkout (or set `XBOX360_PLATFORM_BASE` to its
absolute path). Its commit and package manifest must match the lock. Supply a
legally obtained US Smash Bros. ROM locally; the ROM is never committed. Run
these commands from this repository root in PowerShell:

```powershell
& ./tools/fetch-sources.ps1
& ./tools/fetch-dependencies.ps1
& ./tools/setup-host-deps.ps1
& python -B tools/empty-owned-generated.py --clean
& ./tools/build-assets.ps1 -Rom 'C:\path\to\your\Super Smash Bros. (USA).n64'
& ./platform/xbox360/build.ps1 -Regenerate -Rebuild
```

`fetch-sources.ps1` checks the BattleShip commit and its three submodules;
`fetch-dependencies.ps1` checks out every exact dependency commit. For an
existing checkout, `fetch-dependencies.ps1 -VerifyOnly` checks without changing
it. The cleanup script preserves the old XEX and receipts, then empties only
named generator/build outputs and generated project files; `--list` previews
the targets. It retains pinned source and host dependency caches.
`build-assets.ps1` produces owned game archives from the user's ROM.
`build.ps1 -Regenerate` runs the named projection owners and assembles the
generated project; `-Rebuild` compiles the native projects and links a new XEX.
It then verifies the native link and copies the owned archives beside
`scratch/application-xdk/native/build/Smash360.xex`.

The generated source, project, compiler objects, logs, XEX, and assets live
under `scratch/` or `dist/`; they are reproducible outputs, not source authority.
The source-control checkpoint never contains Xbox SDK files or ROM data. See
`platform/xbox360/` and `tests/` for the adapter contracts and focused checks.
