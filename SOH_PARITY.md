# SoH360 platform and Fast3D parity audit — 2026-09-21

This compares current, read-only `D:/Projects/SoH360` with the owned Smash360
platform and generated BattleShip adapters. The previous port had the core
native backend but missed interpreter-side optimizations. Individual log fixes
did not substitute for this audit.

Donor file identities are recorded in
`scratch/evidence/soh-parity/fast3d-donor-files.json` and
`graphics-donor-hashes.json`. Current native graphics, ImGui, platform,
save-worker and audio donor copies match SoH. Builds consume only owned copies;
no reference project is a mutable build dependency.

## Transfers in this pass

| Area | Transfer and BattleShip contract retained |
|---|---|
| Vertex positions | Bounded SoH VMX transforms with exact separate arithmetic and original scalar fallback. Source aliases retain original read/write order. |
| Clip flags | SoH vector clipping adapted to keep Smash's near-plane bit 16 and write only the clip byte, preserving padding. |
| Replacement matrices | SoH vector s16.16 quantization for accepted values; original exceptional conversion and matrix-stack behavior remain. |
| Conversions and lighting | Exact signed/unsigned 16-bit tables, owned light RGB float cache, batch-invariant fog/texgen inputs and guarded exact double-product division by 127. |
| Repeated normals | Directional RGB/generated-UV reuse within a vertex load. Positions, ordinary UVs, alpha, fog and clip remain vertex-specific. |
| Generated texture coordinates | SoH's four-state exact-key shade cache for bounded directional texgen; positional and exceptional inputs keep the original path. |
| Vertex publication | Donor FPR byte stores and finite fog select; RGB reads follow independent arithmetic. Every vertex is fully published before the next vertex/command. BattleShip's window aspect factor is computed once per eligible batch. |
| Shader metadata | Cache immutable API metadata per backend/program/clamp variant; refresh on backend Init. Clip parameters queried once per Init. |
| Combiner lookup | Inline previous-key hit, cold map lookup/creation; full BattleShip three-word key and original pool ownership. |
| Triangle packing | Pack corresponding attributes for three rows together. Reuse value-keyed material constants; shade and distance-dependent LOD remain correct. Preserve Smash primitive depth, blend/fog alpha, framebuffer UVs, texture masks/extents and stream layout. |
| Texture binding | Six independently certified native bindings. Hash recycled source contents before reuse. Flush before changed bindings, stale contents, uploads, eviction, framebuffer selection or native shader creation. |
| XDK native texture selection | Literal slots 0–5 avoid the SDK's variable-shift microcode path, with original fallback for other indices. |
| Timing | Cache successfully validated QPC frequency per native thread, retaining exact timestamp arithmetic and failure retries. |
| Audio diagnostics | Queue owned scalar snapshots and format on the existing SoH-derived diagnostic worker. PCM, mixer and submission ownership unchanged. |

The material-pipeline cache keeps the original reconciliation as its cold path.
It checks the complete applicable material/geometry/render-state values and
samplers before reuse. A dirty used texture always runs its real import/hash;
unused dirty flags remain untouched. New shader, framebuffer, external API and
GUI operations invalidate the certificate. Primitive depth, per-vertex UVs,
area accounting and packing still execute for each accepted triangle.

## Already present

Current SoH native shader/state/constant caches, shader binary persistence,
deferred GPU resource release, exact small-upload reuse, sampler restoration,
EDRAM tiling/resolves, framebuffer lifetime, native presentation, XInput,
XAudio2 output, storage mounting, diagnostics worker and XDK compiler policy
are retained. Earlier passes already brought over cull/area projection reuse,
cold triangle emission, material geometry math, byte tables, bounded FPR light
accumulation, command-stack access, interpreter dispatch ownership and bounded
display-list lookup caching. Detailed contracts are in the three subsystem
audits under `scratch/evidence/soh-parity`.

## Deliberate differences

- SoH's old two-slot renderer and shader generator cannot replace BattleShip's
  six-slot, Prism-generated shader contract. The native Xbox implementation is
  shared; Smash's current combiner, texture and framebuffer semantics remain.
- SoH's material-restoration shortcut can clear texture-dirty flags. Smash must
  retain those flags and content checks because relocatable assets reuse CPU
  addresses. No value/pointer cache may suppress a required import/hash.
- SoH's lazy attributes across commands leave some loaded-vertex fields pending
  until a triangle or ModifyVertex consumes them. BattleShip exposes its RSP
  state. This pass preserves fully published command outputs and transfers
  eager within-command reuse and conversion scheduling instead. The donor's
  specialized directional lit/fog path is not a replacement for Smash's
  positional lighting or exceptional arithmetic.
- SoH's aspect division helper is not copied into Smash's different formula.
  The exact existing BattleShip scale and multiplication are hoisted instead.
- SoH's game audio worker, metadata-only N64 thread functions, OoT arena and
  asset-eviction policy belong to different game contracts. BattleShip retains
  its real mixer, fibers/message queues, scheduler and resource ownership.
- Diagnostic immediate-presentation/headroom mode and synthetic donor scenes
  are not production optimizations. Native cadence and the real game path stay.

The FPSCR rounding mode is read through a seven-instruction native leaf derived
from the installed XDK. The CRT query also calls kernel exception handling and
is deliberately excluded from the hot path. Nonnearest modes retain scalar
position/quantization and division. The large texgen cache is owned by each
Interpreter to stay within XDK TLS relocation limits; small value caches remain
native TLS. No cache retains a game resource or borrowed vertex pointer.

## Validation and remaining evidence

Differential tests execute authoritative BattleShip blocks and their generated
Xbox counterparts. They cover complete RSP state, aliases, exceptions, cache
mutation/lifetime, queued draw state and packed vertex bytes. Donor VMX source
also runs through an explicitly test-only host lane model; real XDK compilation
and PPC disassembly verify native instructions. These are complementary checks,
not a substitute for console execution.

The latest incoming hardware log contains an appended run; its second run has
mixed heavy windows at roughly 56 and 55 FPS, not a complete isolated Yoshi
sample. It is preserved in `scratch/evidence/hardware-import-diagnostic-20260921`.
New `FRAME_WORKLOAD` command-count bands use existing frame timestamps to
separate heavy and light frames without per-command timing additions.

The final XDK build, linked-code checks, all 36 Fast3D tests and both
scope/workload tests pass. No new hardware or Xenia run was performed for this
audit. Final XEX identity, build commands and verification receipts are recorded
in `BRINGUP.md`. Physical performance and visual validation remain required.

Smash owns game behavior; BattleShip owns its native adaptation; Fast3D and
libultraship retain their interfaces; Xbox owns platform implementations.
