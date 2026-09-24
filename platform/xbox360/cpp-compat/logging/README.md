# Current spdlog source projection for Xbox 360

The core lowering algorithm now lives in Shipyard's
`python/xbox360_platform/logging_core.py`. This directory supplies Smash's
pinned input and selects its existing eager overload and fmt4 ABI policy.
The queue projection and native support remain separate consumer inputs.

The generator adapts the actual pinned spdlog 1.16 headers, retaining current
logger, async message/thread pool, registry, backtracer, rotating file sink,
stdout sink, pattern formatter, and ring/blocking queue algorithms. No donor
logger or printf replacement is used. Upstream stays read-only. Exact source
SHA256 locks reject changed input; manifests record source/output/support hashes
and generated headers map original and transformed regions with #line directives.

Run `python tools/prepare_logging_xdk.py`. Put these include roots ahead of
original spdlog: `scratch/logging-xdk/core-include`,
`scratch/logging-xdk/include`, and `upstream/dependencies/fmt-xdk`. Compile the
native implementations `cpp-compat/async/native.cpp`, `cpp-compat/chrono/chrono.cpp`,
and `platform/xbox360/environment.cpp` in the final target. All paths here are
relative to the project except cpp-compat, which is under platform/xbox360.

The preserved actual Context initialization contract is queue8192, one worker,
blocking overflow, configured severity, source_loc, 10MiB rotating file with ten
backups, pattern `[%Y-%m-%d %H:%M:%S.%e] [%@] [%l] %v`, info flush in release,
registration/default logger, and shutdown after other Context services. Formatting
finishes before enqueue. Current log_msg_buffer owns queued logger-name/payload
bytes and async messages retain logger lifetime until consumption. The actual
250-byte fmt inline buffer remains; moved-from legacy fmt buffers are explicitly
reset to a valid empty buffer before subsequent reuse.

Default logging remains available before Context::InitLogging, including failure
diagnostics. Xbox selects the current uncolored stdout_sink_mt CRT fwrite branch,
with LF newlines. stdout_color_sink aliases map to that same real stdout/stderr
sink; color setters and color-mode constructors are unavailable. Context's desktop
console-allocation calls still require its separate platform transform. Mounted
Xbox drive names are recognized by the actual create-directory routine. Native
getenv uses the root-owned immutable XboxEnv_Get launch environment; initialization
must occur before worker startup. This projection does not invent process IDs:
requesting the %P pattern flag on Xbox throws spdlog_ex.

The formatter is the real official fmt4.1.0 compiler boundary in ../format, with
CStringRef/ArgList/MemoryWriter lowering. This is a documented dependency deviation
from fmt12: diagnostic floating/default-precision differences remain subject to
that boundary's audit. Nonfloating reached examples are compared against original
spdlog/fmt12. Fixed public overloads support up to39 formatting arguments (actual
Fast3D diagnostic maximum found so far). For16..39 they use fmt4's existing typed
ArgArray, MakeArg, packed first16 type tags, and NONE sentinel; actual formatting
still runs in fmt4. Public convenience wrappers beyond39 are not supplied.

Native mutex/CV/thread primitives supply blocking and ownership. Atomic level and
counter operations use locks with original widths; they are not lock-free.
Current old-MSVC no-TLS selection is retained. Startup must initialize the default
registry on its single startup thread before concurrent logging: this old XDK
compiler does not guarantee thread-safe local-static initialization. Failed partial
worker creation terminates and joins previously created workers before rethrow;
that failure cleanup is code-reviewed, not fault-injection tested.

Unused timed dequeue and periodic flush APIs are omitted pending timed native CV
support. Variadic logger/sink factory conveniences are omitted; direct constructors,
iterator ranges, registration and init_thread_pool are retained. Wide logging,
std::format and no-exceptions configurations are rejected. Deleted copy operations
are represented by declarations without definitions, so misuse can fail at link
rather than compile. Custom pattern flag constructor overloads cover0..8 arguments.
Original pattern algorithms/flags are retained, except the explicit unavailable
process-ID behavior. Chrono coverage and arithmetic limits are documented in
../chrono/README.md.

Verification commands:

- `python tests/logging/run_queue.py`: original/generated queue comparison; full
 8192-item blocking, FIFO, four producers, overwrite/discard counters/reset and
 shared payload lifetime, plus actual XDK test object.
- `python tests/logging/run_chrono.py`: std::chrono differential signed casts,
 fractional units, UTC epoch and monotonic checks; native clock/test XDK objects.
- `python tests/logging/run_core.py`: original/generated output comparison for
 default diagnostics, levels, source positions, backtrace, formatting errors,
 13/16/39-argument formatting and sentinel bounds, fixed UTC pattern flags,
 file rotation/callbacks, queue8192/block async owned1200-byte payload, duplicate
 registration, default logger, lifetime and shutdown draining; whole test XDK object.
- `python tests/logging/test_generation.py`: deterministic output, hashes,
 provenance, and changed-input rejection.

These are host behavior comparisons and XDK compilation evidence. They do not
establish Xbox execution, final linking, filesystem success, clock accuracy, or
full Context integration/runtime behavior.

Production bring-up found an XDK 21256 /O2 code-generation failure in
async_logger::backend_sink_it_: its final backend_flush_ call returned directly
into EH metadata (guest PC 8244C414). The generator brackets only that function
with optimization off/on; queueing, sink calls, flushing and catch handlers stay
intact. The actual application then progresses through Context, GUI, Xenos and
four OpeningRoom frames (run 20260919-215130-181). Other runtime boundaries above
still require their own evidence. tests/logging/check_xdk_control_flow.py walks
the real linked function's normal PPC control flow, rejects the saved failing
EXE, and accepts the corrected build with both catch handlers retained. The
native build invokes this regression after linking.
