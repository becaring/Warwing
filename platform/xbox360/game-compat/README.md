# BattleShip C compilation

`tools/prepare_game_xdk.py` compiles the pinned BattleShip C sources with the
Xbox 360 XDK compiler. The source manifest selects 486 translation units from
the upstream build. Failed files stay in that selection; an archive is produced
only when all selected units pass.

Use the full build in [the build guide](../../../docs/XBOX360_BUILDING.md) for
dependency ordering and application linking. For focused checks from the root:

```powershell
python tools/game_source_manifest.py
python platform/xbox360/game-compat/verify.py
python platform/xbox360/game-compat/verify_bool.py
python platform/xbox360/game-compat/verify_narrow.py
```

These checks require the parser packages specified in the build setup. Set
`XEDK` for your SDK path and `SMASH_HOST_VCVARS` for a different host compiler.
`--source` selects an exact manifest path for a targeted compile.

Source overlays are applied before preprocessing. The staged source tree keeps
quoted includes from bypassing an overlay. Conflicting replacements are rejected;
combine them in the projector first. `staged-inputs.json` records the original
and generated hashes. Do not edit the staged tree or upstream source.

The shared Shipyard C lowerer handles XDK syntax restrictions. Game selection
and endian adjustments remain in this repository. Preserve the target layout
checks: `Gfx` packets must remain eight bytes, boolean fields must keep their
expected size and conversion behavior, and floating-point constants must retain
their bit patterns. A passing compile does not establish rendering or gameplay.

The [archived audit](../../../archive/subsystems/game-compat/README.md) retains
the detailed transformations, source-staging API, and recorded verification.
