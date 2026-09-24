# Pinned BattleShip contract audit

2026-09-19. Read-only inspection, not runtime validation. Paths below are relative
to `upstream/BattleShip` unless marked donor. See BRINGUP-MAP.md for ownership.

## Rendering

| Requirement | Evidence | Necessary donor adaptation |
| --- | --- | --- |
| Class ownership | `libultraship/include/fast/backends/gfx_rendering_api.h:59`; `src/fast/Fast3dWindow.cpp:58` deletes backend objects | Current virtual backend objects, not a facade exposing the old C table or a replacement interpreter. |
| Full shader identity | `gfx_rendering_api.h:29`: two uint64 IDs, filtering, sRGB; spaceship comparator | Explicit equivalent comparisons for XDK; full identity in native shader cache. Donor gfx_xenos.cpp:305 takes uint32 second ID. |
| Shader generation | `libultraship/src/fast/backends/gfx_direct3d11.cpp:1485,1535`; source `shaders/directx/default.shader.hlsl` | Current Prism/resource generation semantics must survive conversion to Xbox SM3. Donor's string substitutions target an older procedural generator. |
| Texture slots | `libultraship/include/fast/interpreter.h:101`: six; HLSL mask slots 2/3 and replacement blends 4/5 | Donor gfx_xenos.cpp:377 rejects slots above one. Expand backend ownership/state where this current contract is used. |
| Upload extent and source stride | `libultraship/src/fast/interpreter.cpp:1692,1869,2197,2287` | Preserve natural padded row stride separately from tile/mask-clamped uploaded width. IA4 digits can be 4x7 in larger TMEM rows. |
| UV/cache identity | `interpreter.cpp:3421,3670`; `interpreter.h:181`; `interpreter.cpp:2615` | Retain mask/tile dimensions in cache keys, shifts, origins, mirror and clamp scalars. Donor native addressing can consume these outputs. |
| Palette | `interpreter.cpp:4225` | Retain TLUT eight-byte rounding and lazy endian fixup boundary. |
| Primitive depth | `interpreter.cpp:3511,3650,4673` | Preserve primitive Z / 65535 and z=depth*w, including rectangle Z enable. Donor clip parameters zero-to-one Z remain appropriate subject to runtime verification. |
| Depth write without comparison | `interpreter.cpp:3224`; pinned DX11 `gfx_direct3d11.cpp:707` | Enable Z if test OR write; use ALWAYS if comparison disabled. Donor gfx_xenos.cpp:446 currently enables Z only when test=true. |
| Z-image redirect | `interpreter.cpp:3247` | Real color-write mask operation with correct state-cache invalidation. Do not use the default no-op virtual method. |
| Persistent framebuffer | `interpreter.cpp:7183` | Preserve game color while clearing depth. Clear only pillarbox strips. Donor gfx_xenos.cpp:776 clears both attachments. |
| Lifecycle/copy/readback | `gfx_rendering_api.h:90-126` | Implement reusable FB destruction, rectangular copies, independent clear flags and RGBA5551 CPU readback using donor resolve primitives. Whole-target MSAA resolve does not implement arbitrary copy rectangles. |
| Window | `gfx_window_manager_api.h:6`, `Fast3dWindow.cpp:153` | New lifecycle/query, mouse, position/refresh and IsFrameReady operations. Preserve BattleShip frame loop; old callback main_loop no longer owns it. |

Donor mechanics to keep: EDRAM color/depth preservation and per-sample restore
(`gfx_xenos.cpp:618`), persistent draw-buffer lifetime, Xenos RGBA upload
(`:424`), wrap/mirror/clamp (`:181`), sampler cache-hit restoration (`:377`).
Sampling orientation must be verified; clip-space inversion alone does not
prove framebuffer texture orientation.

Existing pinned approximation: `interpreter.cpp:4699` skips redirected textured
rectangles. Preserving it does not establish full RDP emulation. Postprocessing,
custom shaders, six-slot paths, copy scaling/orientation and endian conversions
remain untested. None have been silently declared supported.

## Resources and byte representations

| Stage | Source | Representation and ownership |
| --- | --- | --- |
| ROM decode | `torch/src/factories/ssb64/RelocFactory.cpp:115` | BE reloc table and external IDs; VPK0 decompression; payload remains N64 bytes. |
| O2R entry | `torch/src/factories/BaseFactory.cpp:3`, `RelocFactory.cpp:87` | 0x40 LUS header marks exporter endian. Metadata is exporter-endian (LE on this Windows host), copied payload stays BE. |
| ZIP/load | `libultraship/src/ship/resource/archive/O2rArchive.cpp:22`, `ResourceLoader.cpp:233` | Header-driven reader; preserve names, resource type/version and ownership. |
| Smash RELO | `port/resource/RelocFileFactory.cpp:5`; registration `port/port.cpp:1122` | Type 0x52454C4F, version 0; reader decodes ID, chains, dependencies and size; payload copied unchanged. |
| Relocation | `port/bridge/lbreloc_bridge.cpp:314,517,650,723,757` | ID/path lookup, game-heap copy, decode, chain walks, dependency loads, token writes and cache invalidation remain BattleShip-owned. |
| Native fixups | `port/bridge/lbreloc_byteswap.cpp:968,1008,1026` | Current blanket word swap plus specialized halfword/byte restoration assume LE. Audit every entry, including lazy texture/vertex/TLUT fixes. Texture deswizzle is semantic, not automatically removable on BE. |
| Audio | `port/bridge/audio_bridge.cpp:244,268,299,554` | LUS BLOB wrapper; CTL/SBK/FGM field-wise BE decoding into native structures. TBL ADPCM and sequence streams remain bytes. |
| Particles | `port/bridge/particle_bank_bridge.cpp:162,200,259,359` | BE headers/offsets; unconditional swap helpers need host-endian correction; pixels/palettes retain N64 layout. |
| PCM | `port/audio/audio_playback.cpp:206`, `port/port.cpp:1047` | Native signed 16-bit stereo at 32000 Hz. |
| Frame snapshots | `port/bridge/framebuffer_capture.cpp:100,159,165,171` | Force offscreen game FB, flush, GPU-copy persistent snapshot, associate CPU ranges and UV subrects. This current capture path is not a BE16 CPU readback substitute. |

`F3DGfx` words are uintptr_t (`libultraship/include/fast/lus_gbi.h:1143`).
Xbox commands are eight bytes. Keep normalization (`interpreter.cpp:157`), token
resolution before segmented addressing (`:5045`), and runtime list stride
`offset / 8 * sizeof(F3DGfx)` (`:5646`). Do not hardcode desktop 16-byte widening.

XDK preprocessing confirmed `Endianness::Native = Little` in the unmodified
`libultraship/include/ship/utils/binarytools/endianness.h`. Evidence:
`scratch/audit/endianness-xdk.i`. Recognize Xenon explicitly in centralized endian
compatibility before runtime loading; do not compensate by swapping whole files.

## Boot dependencies

The canonical US archive contains 2132 reloc resources; JP has 2107. Include
all required audio blobs from `yamls/us/audio.yml` and particle banks from
`yamls/us/particles.yml`, plus transitive reloc dependencies.

OpeningRoom explicitly requests IDs 52, 63, 56, 57, 58, 59, 75, 90 at
`decomp/src/mv/mvopening/mvopeningroom.c:24`, and loads effects/fighters/Boss at
`:1429`. Without a controller the scene path includes reloc file 169. An archive
containing only the eight opening files is not a valid boot package.

Source-generated inputs include reloc headers/tables (`CMakeLists.txt:314`),
credits encodings (`:325`) and shader `f3d.o2r` (`:1092`). These can be generated
without a ROM. They do not replace BattleShip.o2r's ROM-derived content.
Optional from-source archive loading is opt-in, and the named
`tools/build_reloc_resource.py` is absent at this revision; do not assume that
path removes the ROM dependency.

## Compiler probe evidence

The actual pinned `port/coroutine_win32.cpp` was compiled with XDK, not an
invented scheduler. Original source fails because windows.h is absent; changing
only that include to xtl.h exposes unsupported thread_local at original line 39.
Replacing that storage specifier with donor-proven `__declspec(thread)` produces
`scratch/audit/coroutine-xdk-tls.obj`. Generated text retains a #line mapping.
Logs are under `scratch/logs/coroutine-*-compile.log`.

This is object-compilation evidence only. No linker, nested-fiber execution,
queue synchronization, Xbox runtime, GPU output or hardware claim follows.
The generated probe is not linked into any application and is not a second
game loop. No game or upstream production files were edited.

The lexical desktop/compiler inventory is `scratch/audit/source-candidates.json`:
4031 matching lines across 300 files. It includes inactive platform branches and
comments; it is a review worklist, not proof that every match executes at boot
or an exhaustive semantic classification of all portability work.
