# Hardware stage profiling

The normal XDK build compiles full-profiler scopes and counters out entirely.
Use `platform/xbox360/build.ps1 -FullProfiling` to compile them in; that diagnostic
build enables `SMASH360_PROFILE` by default. Set `SMASH360_PROFILE=0` in
`game:\smash360.env` for a runtime-disabled diagnostic comparison. It keeps normal gameplay, rendering, cache verification, input,
scheduler, resolution and MSAA behavior. The existing broad frame/audio logs
remain. No GPU fence, readback or idle wait is added.

`platform/xbox360/package.ps1 -ProfileDisabled` writes both `SMASH360_PROFILE=0`
and `SMASH360_PROFILE_DETAIL=0` into the hardware package. It is mutually
exclusive with `-ProfileDetail`. Copy the resulting `smash360.env` with the XEX;
otherwise an old console environment file can leave the expensive scopes on.
The fully populated Yoshi intro produced an estimated 5.540 ms/frame of active
scope overhead in an earlier detail capture. Runtime disabling still leaves
scope branches and stack traffic compiled in. The normal build now removes
those sites; its console benefit must be measured separately. Startup logs
`PERF full_scopes_compiled=0` or `1`. Environment variables cannot restore
compiled-out scopes. Build/package receipts bind this option to the XEX hash.

This adapts SoH360's low-word PPC time-base scopes, thread-local counters,
observer probe, copied report snapshots and background diagnostic transport.
The inspected donor files were `platform/xbox360/perf_trace.h` (SHA256
`80D580E9DDBDB7CE5A2FDC8455EEB624DD47924390037FA619729DCE8771A556`) and
`perf_trace.cpp` (`3A95CB2173B75FB2E99414CBD52A498ED70B2ABD3BEDFAC6C9151ADB660427CE`).
The owned graphics donor already contains the native draw/upload/store/restore/
shader/depth scopes, which are now retained instead of stripped. The existing
owned SoH-derived diagnostic worker performs formatting and file writes.

`tools/profile_projections.py` inserts scopes into pinned BattleShip/LUS source
through the normal hash-checked generators and their source-line mappings.
Upstream and reference files are not edited. Xbox-only `runtime/perf_trace.*`
owns collection and formatting. Its only accounting extension to the donor
scope is subtracting nested instrumented child durations to report self time.

Each complete report has matching `PERF window=N` and `PERF end window=N` lines.
All section milliseconds and work counts are normalized by the number of
presentations in that reporting window, not game ticks or fighters. A section
with no calls is omitted. Shader cache counters are explicitly cumulative;
native state/upload/clear counters cover the current window. Framebuffer
dimensions describe the currently published game texture at capture time.

- `inclusive_ms` contains nested scopes; do not sum that column.
- `self_ms` excludes nested instrumented scopes. It still includes uninstrumented
  descendants, scheduling delays and any waits in the measured API call.
- `max_call_ms` is the longest individual invocation, not the worst frame.
- `draw_primitive_up`, `texture_lock`, `depth_lock`, `end_tiling`, and
  `explicit_gpu_idle` locate possible synchronization costs. They do not measure
  GPU execution independently. Restore-quad native drawing is included in
  `restore_quad`, not the game-triangle DrawPrimitiveUP row.
- `texture_hash` measures BattleShip's required content checks on recycled
  memory; `texture_hits/misses/stale` explain whether import/upload is repeated.
- Matrix/vertex/triangle, display-list normalization and readable-pointer
  checks remain the actual BattleShip operations. Timing them does not establish
  that any operation can safely be removed.
- `command_step` contains each real opcode dispatch. `dl_bounds` separates its
  existing walk-bounds-check block, and `gbi_trace` measures registered callback
  invocations. Their nested costs are removed from `command_step` self time.
- Native sampler/constant suppression and upload reuse report existing SoH
  optimizations, with no change to reuse decisions.
- Shader creation is split into generator, Xbox source lowering, code-cache
  lookup/store and real compiler time. `shader_compile` only surrounds a real
  D3DXCompileShader call after a binary cache miss.
- `PERF observer` estimates flat scope overhead using 1024 empty scopes outside
  measured frames. It is a lower-level estimate, not a correction subtracted
  from timings; nesting, count increments, cache effects and compiler-generated
  code changes are not fully modeled. Use the disabled run to check perturbation.
- `DIAGNOSTIC report` records producer, queue and worker costs. Reporting work
  appears in the following broad logic interval. A counter/QPC units check uses
  SoH's startup test; gameplay clocks retain their existing implementation.

Start at 100% internal resolution / 1x MSAA with warm shader assets. Record a
light fight and a busy fight for at least 20 seconds each. For controlled
comparison keep stage, fighters, camera and options as similar as practical;
then repeat the expensive scene at lower resolution. Menu/intro windows and
transition or shader hitches must be separated from sustained fighting. The
report does not infer fighter count or scene identity: note those alongside the
log/video. Xenia confirms diagnostic execution, not hardware performance.

`tests/graphics/test_perf_scope.py` executes the production scope accounting
with an injected clock for nesting, recursion, early returns, low-word wrap,
disabled mode and counters. Native build/link checks and a real runtime log
are additionally required; a host accounting test is not runtime proof.

## Optional interpreter detail (schema 2)

First build with `build.ps1 -FullProfiling`. Set `SMASH360_PROFILE_DETAIL=1` in `game:\smash360.env` to attribute handler
costs. It defaults off; `SMASH360_PROFILE=0` disables both levels. The package
script accepts `-ProfileDetail` to produce a reproducible diagnostic env file.
Startup logs both settings in `PERF schema=2 enabled=... detail=...`.

Detail adds the actual temporary weak-owner acquisition, reloc range/ID lookup,
runtime vertex/texture repair, bounds generation acquire and locked range scan.
Bounds counters separate hits, misses, visited ranges, found ranges, unknown and
walked-past results. The original generation ordering, mutex, ownership lifetime,
classification and scheduler callback are unchanged.

The dispatch tail has 256 opcode slots. Each window prints its busiest eight by
self time as `PERF opcode=XX`, followed by `opcode_other` containing the omitted
self time and calls. Add the remainder when checking total self accounting;
never sum inclusive costs. Nested operations can dominate an opcode even when
its own self time is small. All slots contribute to observer/call totals.

Detailed execution was verified before the endian optimization in Xenia run
`20260920-173207-860` (evidence in `scratch/evidence/interpreter-detail`). Texture
repair self time was 1.24-1.277 ms/frame in three sustained intro windows;
the startup window was 6.224 ms/frame. Those are emulator measurements, not
console predictions. Bounds scans also repeatedly returned UNKNOWN, which the
existing one-hit cache does not retain. Both findings identify real executed
operations; only the endian work has been removed at this stage.

Detail can substantially perturb timing: one recorded Xenia window estimated
2.232 ms/frame of scope overhead, versus 7.035 ms summed measured self time.
Per-range counter updates and changed code layout are not fully covered by that
estimate. Compare equivalent detail settings and run a profile-disabled control.

## UNKNOWN bounds-cache correction

The Xbox projection now caches a proved UNKNOWN interval as well as the existing
positive hit. Each call still acquires the unchanged registry generation. A
locked miss intersects the gaps outside every registered range and every
walked-past window; only a final UNKNOWN result publishes that interval. Resizing,
registering or removing ranges invalidates it through the existing generation.
The original scan remains authoritative for every cache miss and overlapping
positive ranges still take precedence over walked-past classification.

`bounds_cache_hits` now includes both positive and UNKNOWN hits.
`bounds_unknown_hits` is the UNKNOWN subset; `bounds_unknown` counts UNKNOWN
results from a full scan only. `bounds_cache_misses`, `bounds_scan_entries`,
`bounds_scan_found` and `bounds_walked_past` retain their meanings. Compare the
new unknown-hit count against avoided scans, not against frames or fighters.
The generation-acquire implementation is unchanged, so its per-call cost is
not expected to disappear. Physical-console confirmation remains required.

## Acquire and dispatch ownership correction

After console confirmation of the UNKNOWN cache, the owned finite atomic
wrapper now honors acquire loads with the XDK acquire interlocked primitives.
Generation reads stay atomic and ordered; other operations retain their prior
fences. `bounds_generation` still measures the same real read. It should not be
interpreted as eliminated work: the reservation operation remains.

The 90 temporary-owner handler sites now borrow from one strong owner scoped
around the existing command walk. `interpreter_owner` retains its call sites,
so it now includes the borrowed-pointer lookup and observer overhead. Acquiring
and releasing the one dispatch pin falls in the enclosing Fast3D self time.
Outside dispatch or after instance replacement, the original weak-lock fallback
still executes. No opcode or triangle behavior changed. Both optimizations
still require physical-console measurement. Keep detail settings equal when
comparing; use `SMASH360_PROFILE=0` for an uninstrumented control.

## Sampled triangle phases

`package.ps1 -ProfileDisabled -TriangleTrace` keeps the expensive full profiler
off and sets `SMASH360_TRIANGLE_TRACE=1`. `TRI_TRACE` samples approximately one
in 64 real GfxSpTri1 calls using a nonzero xorshift state rather than a fixed
triangle ordinal. Early cull returns are included. Phase boundaries preserve
all existing work and state: cull, raster state, combiner lookup, texture state,
shader state, depth/diagnostic preparation, RCP area, vertex pack, finish/flush.

Each report contains total calls, selected samples, sampled phase visits and
raw ticks. Estimated phase milliseconds/frame scale by calls/sample_count/frames,
not by phase visits; uncommon branches therefore do not get inflated to every
triangle. Estimates include probe overhead and sampling variance. Do not treat
them as exact CPU/GPU splits or sum them with inclusive full-profiler sections.
The normal FRAME record remains the measured overall result. The selection
counter and inactive phase checks add some overhead even to unselected calls;
this mode is diagnostic and disabled unless explicitly requested in the env.

The first console sample has 4,185 triangle requests/frame and estimates 6.28 ms
inside triangle phases against 21.126 ms render. This leaves approximately
14.8 ms outside those phases, subject to sampling error. The normal build now
removes full-profiler code even when runtime-disabled. Keep the triangle sampler
enabled for the next comparison; this does not establish that profiling code
accounts for all remaining time.

`tests/graphics/test_profile_compile_mode.py` uses the actual XDK compiler and
disassembly: a representative nested scope/counter function reduces to only
`addi` and `blr` in compiled-out mode, with a time-base positive control in
full mode. This verifies code removal, not physical-console performance.

## Whole-command sampling

`package.ps1 -ProfileDisabled -TriangleTrace -CommandTrace` also sets
`SMASH360_COMMAND_TRACE=1`. This uses the same SoH-derived clock and approximately
one random command in 128. The original command stack, bounds checks, callbacks,
opcode selection, handlers and all early exits remain authoritative.

`CMD_TRACE` reports measured Run setup, walk and finish milliseconds/frame.
Setup includes framebuffer preparation; finish includes final Flush/composition.
Sampled phases cover debugger/loop work, command fetch, bounds checking, trace
callback and dispatch/handler execution. Handler rows identify actual opcode
bytes and include nested triangle/backend work. Do not add TRI_TRACE times to
handler times or the measured walk total.

Opcode/phase estimates use global calls/sample_count/frames; their individual
sample counts are reported so rare-opcode estimates can be treated cautiously.
Constructor selection/counting, loop condition and destructor tail are outside
the phase estimates but inside measured walk time. Mark bookkeeping is charged
to the following phase and then extrapolated. Both samplers perturb execution;
neither is a zero-overhead benchmark. Unselected commands now use a compiler
specialization of the same command body with phase checks erased; they still
pay selection and the sampled/unsampled choice. The original warning budget is
shared by both instantiations. Disable COMMAND_TRACE separately
for a performance-only comparison; full-profiler scopes remain compiled out.

The tests exercise disabled mode, sample selection, phase/opcode totals, early
exit, counter wrap and measured whole-walk accounting using an injected clock.
This checks instrumentation correctness, not console execution or speed.

The first command capture places 16.176 ms in the walk out of 16.973 ms render.
Estimated fetch/bounds/callback phases are 1.394/2.476/1.353 ms. Estimates exceed
the measured walk when summed with handlers because of sampling/observer cost;
do not treat these as exact recoverable milliseconds. The next build caches
only the current deque slot address, uses native acquire reads for generation,
and removes a redundant TLS cache copy. Generation and address checks still
execute for every command. Compare work counts as well as frame times.
