# Warwing

Warwing brings **Super Smash Bros. for Nintendo 64 to Xbox 360** through
[BattleShip](https://github.com/JRickey/BattleShip) and the shared
[Shipyard](https://github.com/becaring/Shipyard) Xbox platform. The executable and
build scripts retain the `Smash360` name.

The project contains the Xbox integration, compiler projections, dependency
locks, and regression tests. BattleShip provides the game port, its Smash
decompilation-based game sources, libultraship/Fast3D, and Torch asset tooling.
Game data is extracted locally from a supported US ROM supplied by the builder.
ROMs, extracted assets, Microsoft SDK files, and compiled game packages are not
included.

## Status

Native boot and controller-driven gameplay have been demonstrated on Xbox 360,
and the selected Release build has compilation, link-ownership, and focused
regression checks. Development continues on demanding-scene performance, audio
underruns during slow frames, and broader rendering/gameplay validation. A
successful build is not a guarantee of complete compatibility or a fixed frame
rate. Changes to platform code or generated runtime code require validation on Xbox
360 hardware.

The Xbox integration uses Xenos graphics, XInput, XAudio2, and native storage.
Four controller slots are supported. Native keyboard/text entry and Raphnet USB
HID transport are unavailable. Optional desktop postprocessing/slang pipelines
are unsupported; arbitrary custom desktop shaders are not guaranteed to work.

## Building

Build on Windows with Git, Python, CMake, Visual Studio C++ host tools, and an
appropriately installed Xbox 360 SDK. Check out the Shipyard revision selected
by `platform-base.lock.json`; do not substitute its latest revision implicitly.
Follow [Xbox 360 building](docs/XBOX360_BUILDING.md) for source acquisition,
ROM extraction, generation, compilation, and output locations.

## Controls

The enhancement menu uses the Xbox controller: Back/View toggles the menu,
the right stick moves its cursor, A clicks/drags, B right-clicks, LT/RT scroll,
and R3 switches between cursor and D-pad navigation. Game mappings remain under
the port's controller configuration.

## Documentation

- [Architecture](docs/ARCHITECTURE.md): source ownership and runtime contracts.
- [Xbox 360 building](docs/XBOX360_BUILDING.md): prerequisites and commands.
- [Upstream and provenance](docs/UPSTREAM.md): dependencies, credits, and updates.
- [Development](docs/DEVELOPMENT.md): verification and performance work.

## Credits

Warwing builds on the work of BattleShip, ssb-decomp-re, libultraship/Fast3D,
Torch, and their contributors. Xbox platform work also derives from SoH360 and
is maintained through Shipyard. Dependency licenses, copyright notices, and
source provenance retain their original terms; see
[Upstream and provenance](docs/UPSTREAM.md). Super Smash Bros. and its game assets
belong to their respective rights holders. This is an unofficial project.
