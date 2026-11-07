# Architecture

## Source ownership

| Layer | Responsibility |
| --- | --- |
| BattleShip and its selected decomp | Game boot, scenes, scheduler, message queues, resource relocation, synthesis, and game behavior |
| BattleShip libultraship/Fast3D | Port service interfaces, resource loading, controller mappings, display-list interpretation, and rendering contracts |
| Warwing | Smash-specific Xbox adapters, source selections, compiler projections, and their tests |
| Shipyard | Shared Xbox graphics/audio/platform services, compatibility primitives, and reusable source lowering |
| Generated output | Reproducible compiler inputs and build artifacts; never the maintained source owner |

`platform-base.lock.json` selects the Shipyard commit, API, and baseline manifest.
The source and dependency locks identify all other inputs. Preparation applies
maintained transformations to those inputs, keeps source mappings, and stages
the selected application under `scratch/application-xdk/native`.

## Runtime boundaries

The application keeps BattleShip's `PortInit`/`PortGameInit` path, game boot,
coroutine scheduler, and scene manager. Blocking message operations yield and
resume, and VI framebuffer rotation comes before VRETRACE delivery. Platform
services must keep that order. Asynchronous resource operations keep their
completion, failure, and ownership semantics.

Smash synthesis produces native signed 16-bit stereo PCM at its requested
32 kHz rate. The Xbox sink owns queued playback buffers until asynchronous
completion. Changing game ticks, dropping samples, or borrowing transient PCM
storage does not fix audio performance.

Decomp controller storage uses its own compact layout. Translate the larger
libultraship pad representation into it; do not copy it over game memory.
Storage initialization finishes before save and shader-cache consumers use the
mounted paths. Cancellation and bounded recovery stay as explicit failure paths.

## Rendering and memory

- Keep BattleShip's full shader key, six texture slots, Prism shaders,
  texture masks/extents, primitive depth, selective clears, and framebuffer
  lifecycle. Clearing depth must not erase persistent color.
- CPU asset addresses can be recycled. Reusing a texture needs the applicable
  content checks and invalidation; pointer identity alone is not enough.
  Framebuffer changes, external rendering, shader changes, and resource
  destruction must invalidate the cached native state they affect.
- Each display-list command publishes complete observable RSP state. When
  optimizing vertex work, keep alias read/write order, floating-point
  evaluation, rounding fallbacks, and positional-lighting behavior.
- Xbox pointers and `long` are 32-bit, and Gfx commands are eight bytes. Keep
  serialized N64 bytes, archive metadata, and native structures separate.
  Endianness alone does not prove bitfield-layout equivalence, and it does not
  make all repair work dead.
- Positive and UNKNOWN display-list caches belong to the calling thread and
  are checked against an acquired registry generation. Locked scans keep
  overlapping-positive precedence. Only UNKNOWN results publish a proved gap;
  unused gap construction can be skipped after another classification wins.

## Compatibility contracts

Keep the C/decomp and C++ header environments separate. Source lowering must
keep temporary lifetimes, cached range endpoints, initialization, exceptions,
serialization before truncation, and callback behavior. Unsupported APIs must
fail visibly and never return fabricated success. The selected formatter
is narrower than modern fmt; matching diagnostic floating-point output does
not make it equivalent to the full API.

Shared changes belong in Shipyard and are adopted through a pin update and regeneration.

## Module constraints

| Module | Contract |
| --- | --- |
| Async and resources | Blocking and future operations keep completion and failure. Release cached resources outside locks. Drain the worker pool before destroying its mutex; single-worker child loads run inline. |
| Chrono | UTC uses 100 ns ticks from 1970. Monotonic QPC conversion uses quotient/remainder arithmetic to avoid overflow. |
| Config and logging | Keep Config/CVar behavior and `XAUDIO2=4`. Include core logging before queue support and fmt. Eager formatting owns queued text. |
| Controllers | Keep all four ports and the selected non-Raphnet source set. Lower move construction to default construction plus swap for the XDK hash-container constraint. |
| CRT and value types | Use Shipyard's physical format, bounded optional, and variant implementation; do not fork these primitives. |
| Fast resources and Fast3D | Keep Gfx macros on one physical line, all six opcode tables, and Smash resource relocation. |
| Filesystem | Establish the logical working directory before consumers open files. |
| Formatting | The fmt 4.1.0 adapter supports 15 arguments and the spdlog-facing logging calls support 39. These are declared API limits. |
| GUI and input editor | Widget constructors initialize all members. Keep configuration for four controller ports. |
| Hires textures | Keep CRC keys, deterministic ZIP ordering, LRU pins, and per-worker handles. The desktop 512 MiB/four-worker defaults say nothing about Xbox capacity. |
| JSON | Use the shared backend and its conversion contracts. |
| Libultra | Translate into the decomp's six-byte pad layout. Link game message/VI owners first; do not force the competing library objects into the link. |
| Libzip | Use zlib and verify locked source inputs. |
| Port and startup | Keep the complete game source closure, `PortInit`, `PortGameInit`, `PortPushFrame`, coroutines, and teardown. Guard context access during startup. |
| Postprocess | Leave `LUS_POSTPROCESS_TRANSPILER` undefined; do not define it as zero. Unsupported operations use the adapter's failure results. |
| Prism | Use the locked `1de054450e7b3c5f777d2e3dfcb228ad120c329d` source and the host CPython 3.13/tree-sitter toolchain. |
| Thread pool | Keep BS 4.1.0 priority and draining semantics. |
| Game and endian | The game units compile as C. Install the endian overlay before preprocessing; serialized and native representations have separate rules. |
| Graphics and ImGui | Keep the full shader key, six texture slots, and ImGui 1.91.9b with the shared renderer. |
| Input | Keep raw stick values; invert Y with saturation at -32768. Triggers map to 0..32767. Do not apply the deadzone twice. |
| Storage | Initialize the display before the selector. The `smashsave:` container (user 0, 1 MiB, `platform/xbox360/runtime/storage_adapter.cpp`) holds only the save file `ssb64_save.bin` and the shader cache `smash360-shaders.cache`. Config, logs (`ssb64.log`, `smash360.log`), and mods live in `game:\`. Keep overlapped-operation storage alive until completion. |

## Environment lookup

The runtime loads `game:\smash360.env` once, before `PortInit` and workers.
A missing file is normal. Entries use ASCII names and literal, untrimmed values
in `name=value` form. LF and CRLF are accepted; blank lines and lines beginning
with `#` are ignored. Duplicate names, NUL, malformed entries, or input over
1 MiB reject the whole parse. Names are case-sensitive. Reloading is rejected,
and returned pointers stay valid for the life of the process.

## Profiling

Reports cover a window only when its matching end is present. Timings divided
by presentation count give CPU work per presentation. Inclusive scopes
overlap, so they cannot be summed. Self time leaves out nested scopes but
includes waits. A maximum is the longest call, not the longest frame. CPU
intervals around graphics APIs do not measure GPU execution. The
1024-empty-scope observer estimate is diagnostic only; do not subtract it from
results.

Per-opcode reports cover 256 opcodes, eight busy categories, and other work.
Bounds-cache results need an acquired registry generation, and UNKNOWN gaps and
overlapping positive ranges keep their lookup precedence.
