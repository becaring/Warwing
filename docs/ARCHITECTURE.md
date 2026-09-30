# Architecture

## Source ownership

| Layer | Responsibility |
| --- | --- |
| BattleShip and its selected decomp | Game boot, scenes, scheduler, message queues, resource relocation, synthesis, and game behavior |
| BattleShip libultraship/Fast3D | Port service interfaces, resource loading, controller mappings, display-list interpretation, and rendering contracts |
| Warwing | Smash-specific Xbox adapters, source selections, compiler projections, and their tests |
| Shipyard | Shared Xbox graphics/audio/platform services, compatibility primitives, and reusable source lowering |
| Generated output | Reproducible compiler inputs and build artifacts, never the maintained source owner |

`platform-base.lock.json` selects the Shipyard commit, API, and baseline manifest.
The source and dependency locks identify all other inputs. Preparation applies
maintained transformations to those inputs, preserves source mappings, and
stages the selected application under `scratch/application-xdk/native`.

## Runtime boundaries

The application retains BattleShip's `PortInit`/`PortGameInit` path, game
boot, coroutine scheduler, and scene manager. Blocking message operations yield
and resume; VI framebuffer rotation precedes VRETRACE delivery. Platform services
must preserve those ordering rules. Asynchronous resource operations retain
completion, failure, and ownership semantics.

Smash synthesis produces native signed 16-bit stereo PCM at its requested
32 kHz rate. The Xbox sink owns queued playback buffers until asynchronous
completion. Changing game ticks, dropping samples, or borrowing transient PCM
storage is not an audio performance correction.

Decomp controller storage uses its own compact layout. The larger libultraship
pad representation must be translated rather than copied over game memory.
Storage initialization completes before save/config consumers use the mounted
paths; cancellation and bounded recovery remain explicit failure paths.

## Rendering and memory

- Preserve BattleShip's full shader key, six texture slots, Prism shaders,
  texture masks/extents, primitive depth, selective clears, and framebuffer
  lifecycle. Clearing depth must not erase persistent color.
- CPU asset addresses can be recycled. Texture reuse requires the applicable
  content checks and invalidation; pointer identity alone is insufficient.
  Framebuffer changes, external rendering, shader changes, and resource
  destruction must invalidate affected cached native state.
- Each display-list command publishes complete observable RSP state. Maintain
  alias read/write order, floating-point evaluation, rounding fallbacks, and
  positional-lighting behavior when optimizing vertex work.
- Xbox pointers and `long` are 32-bit, and Gfx commands are eight bytes. Separate
  serialized N64 bytes, archive metadata, and native structures. Endianness does
  not by itself prove bitfield-layout equivalence or make all repair work dead.
- Positive and UNKNOWN display-list caches belong to the calling thread and
  are checked against an acquired registry generation. Locked scans preserve
  overlapping-positive precedence. Only UNKNOWN results publish a proved gap;
  unused gap construction can be skipped after another classification wins.

## Compatibility contracts

Keep the C/decomp and C++ header environments separate. Source lowering must
preserve temporary lifetimes, cached range endpoints, initialization, exceptions,
serialization before truncation, and callback behavior. Unsupported APIs must
fail visibly rather than return fabricated success. The selected formatter
compatibility is narrower than modern fmt; diagnostic floating-point spelling
is not full API equivalence.

Shared changes belong in Shipyard and are adopted through a pin update and regeneration.


## Module constraints

| Module | Contract |
| --- | --- |
| Async and resources | Blocking and future operations preserve completion and failure. Release cached resources outside locks. Drain the worker pool before destroying its mutex; single-worker child loads run inline. |
| Chrono | UTC uses 100 ns ticks from 1970. Monotonic QPC conversion uses quotient/remainder arithmetic to avoid overflow. |
| Config and logging | Preserve Config/CVar behavior and `XAUDIO2=4`. Include core logging before queue support and fmt. Eager formatting owns queued text. |
| Controllers | Preserve all four ports and the selected non-Raphnet source set. Lower move construction to default construction plus swap for the XDK hash-container constraint. |
| CRT and value types | Use Shipyard's physical format, bounded optional, and variant implementation; do not fork these primitives. |
| Fast resources and Fast3D | Keep Gfx macros on one physical line, all six opcode tables, and Smash resource relocation. |
| Filesystem | Establish the logical working directory before consumers open files. |
| Formatting | The fmt 4.1.0 adapter supports 15 arguments; the spdlog 1.16-facing surface supports 12. This is a declared API limit. |
| GUI and input editor | Widget constructors initialize all members. Preserve configuration for four controller ports. |
| Hires textures | Keep CRC keys, deterministic ZIP ordering, LRU pins, and per-worker handles. Desktop 512 MiB/four-worker defaults are not Xbox capacity promises. |
| JSON | Use the shared backend and its conversion contracts. |
| Libultra | Translate into the decomp's six-byte pad layout. Link game message/VI owners first; do not force the competing library objects into the link. |
| Libzip | Use zlib and verify locked source inputs. |
| Port and startup | Preserve the complete game source closure, `PortInit`, `PortGameInit`, `PortPushFrame`, coroutines, and teardown. Context access is guarded during startup. |
| Postprocess | Leave `LUS_POSTPROCESS_TRANSPILER` undefined, not defined as zero. Unsupported operations use the adapter's failure results. |
| Prism | Use the locked `1de054450e7b3c5f777d2e3dfcb228ad120c329d` source and the host CPython 3.13/tree-sitter toolchain. |
| Thread pool | Keep BS 4.1.0 priority and draining semantics. |
| Game and endian | The game units compile as C. Install the endian overlay before preprocessing; serialized and native representations have separate rules. |
| Graphics and ImGui | Retain the full shader key, six texture slots, and ImGui 1.91.9b with the shared renderer. |
| Input | Preserve raw stick values; invert Y with saturation at -32768. Triggers map to 0..32767. Do not apply the deadzone twice. |
| Storage | Initialize the display before the selector. Preserve XContent user 0, 1 MiB allocation, save/config paths, and overlapped-operation storage until completion. |

## Environment lookup

The runtime loads `game:\smash360.env` once before `PortInit` and workers.
Absence is normal. Entries use ASCII names and literal, untrimmed values in
`name=value` form. LF and CRLF are accepted; blank lines and lines beginning
with `#` are ignored. Duplicate names, NUL, malformed entries, or input over
1 MiB reject the complete parse. Names are case-sensitive. Reloading is rejected;
returned pointers remain valid for the process lifetime.

## Profiling

Reports cover a window only when its matching end is present. Timings normalized
by presentation count describe CPU work per presentation. Inclusive scopes
overlap and cannot be summed; self time excludes nested scopes but includes
waits. A maximum is the longest call, not the longest frame. CPU intervals around
graphics APIs do not measure GPU execution. The 1024-empty-scope observer estimate
is diagnostic and is not a correction to subtract from results.

Per-opcode reports cover 256 opcodes, eight busy categories, and other work.
Bounds-cache results require an acquired registry generation; UNKNOWN gaps and
overlapping positive ranges preserve their lookup precedence.
