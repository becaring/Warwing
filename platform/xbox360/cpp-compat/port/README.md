# BattleShip port compiler projection

`tools/prepare_port_xdk.py` stages the actual port source closure selected by
`tools/application_source_manifest.py`, then compiles it with the Xbox 360 SDK.
It emits objects and an explicit failure audit, not an executable or boot claim.
Upstream BattleShip and the SoH360 donor remain read-only.

Run from `D:\Projects\Smash360` after generating the canonical owner overlays:

```powershell
python tools/prepare_port_xdk.py
python tests/port-xdk/run_tests.py
python tests/port-xdk/gui_defaults.py
python tests/port-xdk/css_native.py
python tests/port-xdk/resource_enum.py
```

`--prepare-only` stages without compiling. Repeated `--source port/path.cpp`
limits the native audit to selected source paths. A limited audit replaces
`compile-audit.json`, so retain a separate copy when comparing with a full run.

## Inputs and provenance

The generator validates selected source hashes from the application manifest
and additional header hashes from `headers.lock.json`. It composes endian,
startup, C-language, Fast3D, config, resources, binary reader, audio, root GUI,
controllers, Context, HiRes, and GUI-widgets projections before applying the
owned port transforms. `scratch/port-xdk/staging.json` records full provider
chains and hashes, including superseded providers. Generated text has mapped
`#line` locations; `compile-audit.json` records driver/helper/staging hashes,
exact commands, source hashes, diagnostics, and successful PPC object hashes.

The final source closure is a physical mirror under `compile-tree`. Sparse
include prefixes alone are insufficient because quoted sibling includes can
otherwise resolve to an unmodified header. Only source/header inputs are
mirrored. For final assembly, consume the `port/` subtree of `composed-overlay`
and compose current canonical LUS owners separately; do not take this staging
copy as authority over another owner's LUS headers.

The compile flags include the pinned US CMake definitions `NON_MATCHING`,
`NON_EQUIVALENT`, `AVOID_UB`, `PORT`, `F3DEX_GBI_2`, `_LANGUAGE_C`, `N_MICRO`,
`_USE_MATH_DEFINES`, `CIMGUI_DEFINE_ENUMS_AND_STRUCTS`, and
`PORT_HIRES_ENABLED=1`. Region and archive identity are US/BattleShip. Scripting
is disabled by the approved target contract. Updater version and asset recipe
identity remain final startup/build inputs, not fabricated audit values.

## Preserved contracts

* The actual coroutine, scheduler/game loop, audio glue, relocation, particle,
  interpolation, save, logging, and HiRes implementations are compiled.
  Environment reads use the real `XboxEnv_Get` service. Save resolution retains
  override, Context application directory, and current-directory fallback with
  retry after a failed resolution.
* Shipyard's physical atomic header supplies the reached integer/bool operations
  with native aligned interlocked instructions and explicit PPC fences. Its
  clock sleep helper rounds waits upward and rechecks the monotonic clock.
* Actual `port_log.c` uses the central C99 `Smash360_Vsnprintf` adapter, preserving
  full output and embedded NUL bytes. The final link must exclude the older
  `port_log.c` member from the C archive and use this object once.
* CSS builders write actual native Sprite/Bitmap scalar fields with native
  stores, while original serialized RGBA16 pixel bytes remain big endian.
  Synthetic registration and reuse behavior remain intact.
* GUI lowering uses actual field schemas and typed records. Ordinary default
  initialization and value initialization are distinct; omitted scalar fields
  are zeroed only for value initialization. Variant alternatives, callbacks,
  defaults, and written member order remain the original ones.
* Native menu backend labels cover the actual XAudio2/Xenos enum values.
  Desktop file-browser buttons, background SDL joystick hints, and the excluded
  shader downloader are guarded as complete controls on Xbox. HiRes enable,
  preload, cache-budget, statistics, and texture-dump controls remain present.
* Shader warmup retains all 74 original semantic ID pairs. The constructor form
  is required by the canonical projected `Fast::ShaderPermutation` type.
* The port resource enum drops only `class` while retaining its explicit
  `uint32_t` underlying type. The closed source audit finds one qualified use:
  the explicit uint32 resource registration value. XDK supports the remaining
  fixed-underlying enum and qualified enumerator syntax. Width, unsigned
  ordering, exact RELO value, and high-bit widening have dedicated probes.

## Verification and boundaries

`run_tests.py` executes Win32 ILP32 tests of real logging/CRT, embedded NUL and
long messages, integer-size formats, atomic contention/wrap/CAS, wait rounding,
and finite color conversion. It also compiles PPC probes and checks reservation
instructions plus fences. `gui_defaults.py` compares 210 fields from 12 actual
original/projected GUI option records under default and value initialization.
`css_native.py` checks actual Sprite/Bitmap fields and target layout assertions,
then checks PPC `sth`/`stw` stores without byte-reversed stores.
`resource_enum.py` compares original/projected Win32 high-bit widening and
compiles unsigned width/value assertions with the actual XDK. Actual port
audits enable `/GR` because the production source uses RTTI.

These checks do not execute on an Xbox or establish a final link, renderer
correctness, or boot. The current authoritative native pass/failure count and
earliest remaining source diagnostics are in `scratch/port-xdk/compile-audit.json`.
Final integration supplies `async/native.cpp`, `chrono/chrono.cpp`,
`environment.cpp`, and `crt/snprintf.cpp`; port atomic/timing/color helpers are
header-only. Other owner overlays retain their own platform dependencies.
