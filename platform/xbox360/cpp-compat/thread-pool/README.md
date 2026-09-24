# Pinned BS thread-pool XDK projection

Source: [BS thread-pool v4.1.0](https://github.com/bshoshany/thread-pool/tree/v4.1.0),
commit `097aa718f25d44315cadb80b407144ad455ee4f9`, fetched unmodified into
`upstream/dependencies/thread-pool`. This is the exact version declared by pinned
libultraship. The upstream MIT license remains in that checkout.

`tools/prepare_thread_pool_xdk.py` reads the original header, requires SHA-256
`fed5f7da0bc89fa747e65a8b3896344dc10f57c30d171b51e4fbde820b6d7c03`, and writes
`scratch/thread-pool-xdk/BS_thread_pool.hpp` plus `provenance.json`. Input changes
fail closed before generation. The output contains original method bodies with
`#line` mappings to the original source; the manifest records every selected
method and the generated hash. Source mappings identify original methods; added
or removed compatibility lines can offset individual lines inside those methods.

The retained algorithms are BS's priority queue, task push/pop, pause predicate,
running-task accounting, drain wait, worker loop, initialization and shutdown.
ResourceManager remains unchanged and is not yet compiled against this layer.
There is no replacement ResourceManager, immediate executor, or simulated pool.

## Supported surface

`BS::thread_pool` supports all four original constructors, destructor,
`get_tasks_queued/running/total`, `get_thread_count`, `is_paused`, `pause`, `unpause`,
`purge`, `detach_task`, `submit_task`, and blocking `wait`. `BS::priority_t`, `pr`
priority constants and version macros retain the pinned meanings. Both pause and
priority configuration macros are required, as in ResourceManager's header.
Disabled exception handling, native-handle mode and deadlock-check mode produce
explicit preprocessor errors.

Callable captures and return deduction preserve the normal `submit_task(lambda,
priority)` call shape. Results use centralized `xbox_compat::future<T>`, implicitly
convertible to its `shared_future<T>`. Object and void results are supported;
task exceptions propagate through their promises. Consumers still spelling
`std::shared_future` need the centralized generated namespace adaptation during
future ResourceManager compiler integration; no `std` symbols are injected here.

`reset`, timed waits, `multi_future`, block/loop/sequence helpers, optional TLS
queries, native-handle/thread-id queries and deadlock-check configuration are
outside this bounded projection. Calls to omitted methods fail to compile. A task
must not destroy its own pool or call pool-wide `wait()` from one of that pool's
workers. The original single-waiter `waiting` flag is retained: simultaneous
pool-wide `wait()` callers are outside the verified contract. Shared-future
multi-reader waits remain supported.

The native support reuses `xbox_compat` events, mutexes, condition variables,
promises and joining threads. Hardware concurrency reports Xenon's six hardware
threads; host tests query Windows. No new affinity policy is imposed. Worker
creation transfers a copied `std::function<void()>` into an owned native callback
packet. All shutdown paths signal stop and join before member destruction.

## Recorded lowering and corrections

- Remove attributes and optional APIs; lower aliases and constexpr constants.
- Move in-class member initialization and delegating constructor initialization
  into explicit initializer lists. Private declarations prohibit copies/moves.
- Replace class-template argument deduction with explicit lock types.
- Replace init-capture with an explicit copied callable and ordinary capture;
  replace `if constexpr` with object/void completion specialization. Callables
  must be copyable, as required by the original `std::function` task queue.
- Deduce no-argument callable results with `decltype` and an unevaluated operand
  helper because the installed XDK STL lacks `std::declval`/`invoke_result_t`.
- Replace queue emplacement with construction plus `push`, `make_unique` arrays
  with explicit unique ownership, and thread binding with `std::bind` plus the
  joining native worker. Express the original priority-task cast as `const_cast`.
- Express `while (true)` as `for (;;)` to avoid XDK's constant-condition warning.
- Correct the original worker's completion check at lines 915-919: v4.1.0 drops
  `tasks_mutex` before reading `waiting`, `tasks_running`, `paused`, and the queue.
  The generated worker keeps that mutex held while checking/notifying. Queue
  policy and completion predicates remain unchanged; the unlocked data race is
  removed. This is a synchronization correction, not merely syntax lowering.
- On partial native thread-creation failure, stop/notify/join already-created
  workers before rethrowing. Without this guard, joining ownership would block
  forever while partially created workers wait for tasks during unwinding.

## Verification and limits

Run `tests/thread-pool/run.ps1` and `tools/test_async_compat.ps1`. The pool runner
generates the projection, compiles and runs the same host behavioral suite against
both the original v4.1.0 library and the generated library, then compiles the
generated tests and native primitives to XDK objects. MSVC host builds use
`/W4 /WX`; all child tests have a 30-second deadline. Logs and artifacts stay under
`scratch/thread-pool-xdk`.

Tests exercise ResourceManager's actual capture/result shapes (`this`, copied
identifier/filter, flags, initialization shared pointer; single and vector shared
resource results; void dirty/unload work). They also verify worker identity,
nested high-priority resource submission with available workers, high-before-normal
queue order, paused drain behavior, task exceptions, queued broken promises on
paused destruction/purge, running-task shutdown join, and 1,600 repeated tasks.
Primitive tests cover condition-variable broadcast and void future ownership.

Passing host suites plus XDK object compilation do not prove XDK linking, Xbox
exception runtime behavior, actual LUS integration, or game boot. No separate
test XEX is produced. Partial native creation failure cleanup is reviewed but has
not been fault-injected on either platform.
