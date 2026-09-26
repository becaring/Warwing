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

The application retains BattleShip's `PortInit`/`PortGameInit` path, real game
boot, coroutine scheduler, and scene manager. Blocking message operations yield
and resume; VI framebuffer rotation precedes VRETRACE delivery. Platform services
must preserve those ordering rules. Asynchronous resource operations retain real
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

Subsystem documents under `platform/xbox360` and focused tests describe the
remaining platform-specific details. Shared changes belong in Shipyard and are
adopted through an explicit pin update and regeneration.
