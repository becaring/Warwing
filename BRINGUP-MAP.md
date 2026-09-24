# Smash360 integration reconstruction

Recorded 2026-09-19, before production edits. This is the original reconstruction
map. Current build, visible-boot evidence and known failures are in BRINGUP.md.

## Authority and source lock

Only `D:/Projects/Smash360` is writable for this mission. Reference trees were
inspected read-only. No Bromurokk/Xenos64 Smash port source was obtained or used.
The initially empty destination had no requested source revision recorded.
The official BattleShip checkout and the exact gitlinks it selects are:

| Source | Repository | Commit |
| --- | --- | --- |
| BattleShip | https://github.com/JRickey/BattleShip | `07d04c5a8d3b1b712e2a749cbdd3812588bdb756` |
| Smash decomp, port patches | https://github.com/JRickey/ssb-decomp-re | `2898d4d94e998ddb4e971addf7f6d85a39792f3d` |
| BattleShip libultraship/Fast3D | https://github.com/JRickey/libultraship | `89d9de83a8d09bd7d3b7bc7f8d08554ee2ce8459` |
| BattleShip Torch | https://github.com/JRickey/Torch | `3aa9c9739af95659f19adc73afeb12df93957fc3` |

These are under `upstream/BattleShip`. SoH360's current local Xbox implementation
is the platform donor. Its documented original Shipwright baseline is 4.0.5,
`6e2c38895bb40492bd0361fec76aa83278d3f68a`; that does NOT identify the subsequent
local Xbox changes. Record individual donor file hashes when importing them.
`D:/3Shipsty/OoT-360-Port-Handoff.md` and `Re60-clean/README.md` were inspected as
historical context, not platform authority. Xenia is a validation instrument.

## A. Game-owned code to preserve

Paths in this section are relative to `upstream/BattleShip`.

| Boundary | Actual owner and production path | Xbox integration decision |
| --- | --- | --- |
| Entry | `port/port.cpp:1257` main -> `PortInit` -> `PortGameInit` -> `PortPushFrame` | Adapt platform initialization around this path; do not copy SoH main/frame driver. |
| Context | `port/port.cpp:643` creates `Ship::Context`, initializes logging/config/CVars, window, resource manager/factories, events, control deck and audio | Keep dependency ordering and Smash factory registrations. Desktop first-run extraction becomes host packaging; no fabricated resources. |
| Game boot | `port/gameloop.cpp:546` -> boot coroutine -> `syMainLoop`; `decomp/src/sys/main.c:276` -> idle/thread 5 -> `scManagerRunLoop` | Preserve actual boot and scene manager. |
| Scheduler | `port/stubs/n64_stubs.c` priority service-thread passes, blocking queue yield, SP/DP completion deferral; `port/coroutine.h` nested resume/yield contract | Retain all game scheduling policy. XDK offers CreateFiber/DeleteFiber/ConvertThreadToFiber/GetCurrentFiber/SwitchToFiber. Adapt existing Win32 backend narrowly. |
| VI/frame | `port/gameloop.cpp:682` rotates current/next VI framebuffer BEFORE posting VRETRACE, then resumes service coroutines | Preserve ordering, framebuffer ownership and intentional task deferral. QPC/presentation implementation is platform-owned. |
| Display lists | `port/gameloop.cpp` `port_submit_display_list`, LUS `Fast3dWindow` and `GfxInterpreter` | Keep Smash list normalization, resource/token resolution, scene lifetimes and interpolation paths. |
| Audio | `decomp/src/sys/audio.c`, compiled n_audio sources, `port/audio/mixer.c`, `port/bridge/audio_bridge.cpp`, `port/audio/audio_dma.c`, `port/audio/audio_playback.cpp` | Real Smash synthesis stays. Adapt final PCM sink only. Smash requests 32000 Hz; donor's 44100 Hz is NOT transferable policy. Existing historical silence function is not proof of current mixer operation and must not be substituted. |
| Input | decomp controller service -> LUS `src/libultraship/libultra/os.cpp:14,97,104` -> ControlDeck -> pads | Add Xbox physical input using donor XInput logic, preserve ControlDeck contract and Smash's six-byte GameContPad copy. Never write LUS's larger pad layout into decomp storage. |
| Saves/files | `port/port_save.cpp`, `port/app_paths.cpp`, LUS archive/config paths | Preserve save representation; map application data to native XContent/storage primitives. |

Inherited boot behavior: `decomp/src/sc/scmanager.c:998` changes Startup to
OpeningRoom under PORT. This is BattleShip behavior, not a new Xbox shortcut.
Do not add BootToVSCSS, stage-cycle demo flags, forced scene selection or input
injection. Earliest normal visible output may be the opening room rather than
the N64 Nintendo/HAL startup scene. Report the exact scene actually reached.

## B. libultraship/Fast3D interfaces to retain

This libultraship is much newer than SoH360's 4.0.5 interface. Fast3D uses
`Fast::GfxRenderingAPI` and a window-manager class, not the donor C callback
tables. Keep the current API and adapt donor implementation behind it.
Preserve `Ship::Context`, ResourceManager/ArchiveManager/ResourceLoader,
Smash resource factories, ControlDeck, AudioPlayer and event contracts.

ResourceManager uses asynchronous shared futures and thread-pool work; replacing
these with synchronous success-returning facades is not acceptable. Platform
primitives and compiler compatibility must retain completion, ownership and
failure semantics. Torch is host tooling; O2R remains the runtime archive.

## C. SoH360 Xbox donor implementations

All paths below are under `D:/Projects/SoH360` and must be copied with provenance
into Smash360 before use; no runtime/build dependency may point back to them.

| Donor | Reusable implementation | Contract boundary |
| --- | --- | --- |
| `platform/xbox360/gfx_xenos.cpp` | XDK D3D9 device, shaders, textures, EDRAM resolve, viewport/scissor, draw-buffer lifetime and state handling | Implement current Fast3D virtual methods; preserve newer shader key and framebuffer semantics. |
| `platform/xbox360/shader_cache.*` | Native shader caching | Version keys for the adapted shader generator and full current combiner key. |
| `platform/xbox360/platform.cpp` | QPC timing, native presentation, file/log I/O and XContent storage | Extract platform operations without importing SoH frame or save policy. |
| `platform/xbox360/xinput_controller.*`, `input_xinput.cpp` | XInput polling, axes, rumble, physical slots | Current ControlDeck mapping/device interfaces differ; preserve four-slot capacity. |
| `platform/xbox360/audio_xaudio2.cpp` | XAudio2 voice, persistent bounded buffers, callbacks, backpressure | Implement current AudioPlayer with runtime AudioSettings; use Smash rate/channel/buffering requirements. |
| `platform/xbox360/save_worker.cpp`, `audio_worker.cpp` | XDK event/thread synchronization patterns | Reuse primitives as appropriate, not their SoH job policy. |
| `platform/xbox360/SoH360.vcxproj`, `SoHCore.vcxproj`, `build.ps1` | VS2010/XDK 2010-01 project/link/XEX setup | Generate Smash source manifest deterministically from audited upstream selections. |
| `tools/c89_lower.py`, `prepare_xbox_c.py`; upstream `CompilerCompat.h` | Generated C declaration lowering and narrow old-compiler helpers | Apply only proven compatible transformations; retain original path/line and input hashes. |
| `platform/xbox360/arena_xbox.cpp`, `math_platform.cpp` | Native allocation/math/CRT support | Audit required functions and alignment before import. |

Do NOT import `legacy_messages.cpp`: it explicitly implements SoH's synchronous
polled queues, including OS_MESG_BLOCK returning on empty. Smash requires yield
and resume. Do NOT import `assets.cpp`, `otr_application.cpp`, `frame_driver.cpp`
or Zelda game globals as replacement BattleShip implementations.

## D. Compiler/XDK incompatibilities

XDK installed at `C:/Program Files (x86)/Microsoft Xbox 360 SDK`; donor uses
version 2.0.21256.0, MSBuild .NET 4 and toolset 2010-01. BattleShip CMake requests
C++20 and C11. This is a substantial compatibility task, not a macro-only fix.

- Runtime C++ uses scoped enums, in-class initializers, override/final,
  constexpr, thread_local, uniform initialization, move semantics, range loops,
  generic lambdas/modern templates, structured bindings, filesystem, chrono,
  threads, mutexes, condition variables, futures, optional/variant and current
  JSON/spdlog/ImGui dependencies. Inventory source occurrences before selecting
  transformations; do not downgrade upstream revisions to hide requirements.
- Separate C/decomp and C++ include universes. Decomp libc/PR headers shadow
  modern standard headers; BattleShip already separates bridge types for this.
- Retain ILP32 widths (`long` and pointers 32-bit), packed Gfx command stride,
  token-pointer architecture, alignment and endian/layout contracts. XDK BE
  bitfield allocation must be checked against IDO serialized layout rather than
  presumed equivalent just because both processors are big-endian.
- `coroutine_win32.cpp` needs XDK header selection and verified TLS syntax;
  validate nested coroutine resume/yield and stack preservation, not just a
  successful object compilation. XDK fiber declarations are in winbase.h:1206-1246.
- Gate desktop minidumps/DbgHelp, WASAPI, SDL backends, UWP, RenderDoc, shell
  launchers and host extraction at the platform boundary. UWP support in the
  official source targets later Xbox/Windows and is not an Xbox 360 backend.
- Existing `DISABLE_SCRIPTING` is an upstream-supported option suitable for
  first boot; TinyCC/funchook executable-code targets do not establish Xenon
  support. Any disabled optional desktop integration must be recorded explicitly.

## E. Missing operations and unresolved proofs

Existing donor operations need interface adaptation, not reinvention. Confirmed
new Fast3D requirements include a 64-bit second shader key, color-write control,
selective depth/color clears, rectangle clears and framebuffer lifecycle/copy/
readback. Donor `Clear` clears both color and depth; wrapping it as current
`ClearDepth` would erase preserved Smash frame contents. Implement these as
general backend operations, never game-scene special cases.

Endian work must distinguish archive metadata, untouched N64 byte payloads and
native structures. BattleShip's broad reloc word swapping AND specialized u8/u16
repair helpers assume little-endian hosts. Keep relocation and semantic fixups;
gate only conversions proven unnecessary on Xenon. XDK preprocessing now proves
the pinned LUS header incorrectly selects Native=Little; see CONTRACT-AUDIT.md.

Asset dependency resolved: the user's original US dump normalizes to SHA-1
`e2929e10fccc0aa84e5776227e798abc07cedabf` (NALE). Original dump retained.
Pinned Torch produced the real `scratch/assets/BattleShip.o2r`; ZIP checks and
all 2,132 reloc resource paths pass. See `scratch/audit/rom.json` and
`asset-generation.json`. Actual Xenon resource loading remains to be validated.

## Execution order and evidence gates

1. Lock authoritative revisions, finish subsystem audit and obtain/hash user's
   matching ROM or verify an extracted archive against this pinned recipe.
2. Host-build pinned Torch and produce BattleShip.o2r and generated inputs using
   BattleShip's own pipeline. Verify names, resource metadata and known reloc
   examples on both endian interpretations before Xbox loading changes.
3. Generate Xbox source/build selection, import hashed platform donor files,
   downlevel required C/C++ narrowly with original source mapping. Verify ABI
   sizes/bitfields and real coroutine nested blocking behavior.
4. Integrate Context/resource/factory services, then AudioPlayer and ControlDeck
   Xbox devices, preserving real PortInit -> PortGameInit -> syMainLoop.
5. Implement current Fast3D API over adapted Xenos, including framebuffer and
   full-key semantics. Build the real application XEX; do not create a separate
   renderer or boot-test XEX as a milestone substitute.
6. Run a local copy of Xenia with storage/cache/log paths under Smash360; use
   donor correctness settings (synchronous shader compilation, full resolve).
   Capture initialization logs, real scene identity, actual rendered image and
   controller response. Trace the earliest wrong state at each failure.
7. Stop broad work at genuine visible boot. Record hashes, exact build commands,
   XEX path, deviations and validation in BRINGUP.md. Hardware remains unverified.
