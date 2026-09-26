# Bounded XDK asynchronous primitives

This is a prerequisite for the pinned libultraship ResourceManager, **not its
integration or a BS::thread_pool replacement**. ResourceManager and all upstream
sources remain unchanged. There is no synchronous task facade, completion poller,
standard header shadow, or code injected into `std`.

## Supported contract

Include `native.h` or `future.h`, link `native.cpp`, enable C++ exception handling
(`/EHsc`), and use namespace `xbox_compat`. Both host Windows and XDK use the same
implementation and native Win32-compatible synchronization APIs. `_XBOX` selects
`xtl.h` and the XDK spelling `std::copy_exception`; host selects `windows.h` and
`std::make_exception_ptr`.

| Type | Supported operations |
| --- | --- |
| `mutex` | Noncopyable default construction, `lock()`, `try_lock()`, `unlock()`; native critical section ownership. |
| `lock_guard<M>` | Noncopyable single-mutex RAII acquisition/release. |
| `unique_lock<M>` | Noncopyable single-mutex scoped ownership with explicit `lock()`, `unlock()`, and `owns_lock()`. Misuse throws `logic_error`. No deferred/adopted/moved ownership API. |
| `condition_variable` | `wait(unique_lock<mutex>&)` and predicate overload, `notify_one()`, `notify_all()`. Per-waiter native events; no timed waits. |
| `manual_reset_event` | Noncopyable construction with optional initial signal, `set()`, `reset()`, blocking `wait()`, bounded `wait_for_ms(DWORD)`. Timed wait returns false only on timeout; the `INFINITE` timeout argument is rejected. |
| `joining_thread` | Empty or `(void (*)(void*), void*)` construction, move construction/assignment, `joinable()`, `join()`. Destruction and replacement join outstanding work. Empty `join()` is idempotent. |
| `promise<T>` | Default/move construction, move assignment, `get_future()` once, `set_value(const T&)`, `set_value(T&&)`, `set_exception(exception_ptr)`. Destruction/replacement of an unsatisfied producer signals `broken_promise`. |
| `future<T>` | Empty/move construction and assignment, `valid()`, blocking `wait()`, consuming `get()`, transferring `share()`. `get()` invalidates even when it throws. |
| `shared_future<T>` | Empty/copy/move construction and assignment, implicit construction from `future<T>&&`, `valid()`, blocking `wait()`, repeatable `get()` returning `const T&`. Moving invalidates the source. |
| `future_error` | `logic_error` subclass with `code()` returning the local `future_errc`: `broken_promise`, `future_already_retrieved`, `promise_already_satisfied`, or `no_state`. This is not `std::error_code`. |
| `native_error` | `runtime_error` subclass naming the failed operation; `native_code()` preserves the native error number. |

The supported future result is a non-reference object type, including move-only
objects, or `void`. The explicit `void` specializations use `set_value()` and
`get()` returning void; ownership and exception rules match object results.
Current ResourceManager shapes are `shared_ptr<IResource>`,
`shared_ptr<vector<shared_ptr<IResource>>>`, and void dirty/unload operations.
There are no reference specializations, timed future waits, deferred or
`async` execution, packaged tasks, at-thread-exit publication, allocator APIs,
chrono adapters, general thread callable binding, detachment,
affinity, cancellation, priorities, or hardware-concurrency queries. Unsupported
calls fail to compile; these omissions must be implemented explicitly if a real
consumer needs them. This layer does not claim standard-library completeness.

## Ownership and synchronization

Each promise allocates one reference-counted state with a critical section and a
manual-reset completion event. The producer constructs the value or stores the
exception while holding the critical section, marks ready exactly once, and
signals the persistent event. Readers block in `WaitForSingleObject(INFINITE)`,
then acquire the same critical section before observing the immutable payload.
No event reset, sleeping loop, fake result, or request execution occurs inside a
future. Completion before `get_future()` is valid. A value-construction exception
leaves the promise pending and permits retry.

The last promise/future owner destroys the state, value, event, and lock. Copies
of a shared future retain the same result; a reference returned by `get()` must
not outlive all state owners. Different readers may call `get()` concurrently;
as with standard futures, the same handle must not be moved/destroyed concurrently
with access. Result object synchronization remains the consumer's responsibility.
Competing producer `set_value`/`set_exception` calls serialize, and exactly one
succeeds. `get_future()` serializes with publication. Producer move/destruction
must not race with use of that producer handle.

The broken-promise exception is allocated during state construction so producer
destruction needs no new allocation. Native event signaling failure during a
destructor terminates rather than silently leaving blocked readers. Null
exception pointers are rejected with `invalid_argument`. Other invalid future
operations throw the stated `future_error`.

Workers own their invocation packet independently of the movable thread handle.
Contexts must remain alive until join. The owner supplies any stop signal before
joining; this primitive cannot stop a blocked callback. Uncaught callback
exceptions terminate, so a future-producing callback must capture
`current_exception()` and set its promise. Self-join throws `logic_error`; a
destructor that cannot join terminates. There is no detached worker accessing
destroyed owner state. Native critical sections are recursive internally, but
recursive locking is outside the `mutex` contract, as it is for `std::mutex`.

Condition-variable wait registers a stack-owned waiter under an internal lock
before releasing the caller's lock. Notifications remove and signal registered
waiters under that same internal lock. A waking waiter synchronizes with the
notifier before destroying its event and reacquires the caller's lock before
returning. This prevents registration/release lost wakeups and event-lifetime
races without polling. Predicate overloads loop on spurious notifications. As
with standard condition variables, all waiters must use the same external mutex
and the condition variable must outlive them.

## Provenance and library boundary

The native event, critical-section, and worker-lifetime patterns derive from
these SoH360 references. Their game, queue, save, audio, logging, and thread
placement policies are outside the compatibility layer.

| SoH360 source | Reference SHA-256 |
| --- | --- |
| `platform/xbox360/save_worker.cpp` | `64A194F4AA80399F7CE1D5BEFED876A4F5634C51C3C6D2166D042B3127408B47` |
| `platform/xbox360/audio_worker.cpp` | `9AF7C79E386F1C5347F30E5327E2298300C899C342668CC6A13827A435470538` |
| `platform/xbox360/platform.cpp` | `18ED5127D03E933DF041A33F1691BECF29A058580F335535F3EFCD2C832CD419` |

The donor's shutdown order signals stop, waits on the worker, and only then
closes handles/deletes critical sections. Save completion uses a manual-reset
idle event; that persistent broadcast mechanism is appropriate for future
readers. Donor queued writes and mixer scheduling are not future algorithms.

The pinned LUS dependency declaration selects BS thread-pool v4.1.0. It consumes
standard futures. XDK's installed `exception` header supplies reference-counted
exception transport, and its `memory` header supplies shared/unique ownership;
those implementations are reused. The XDK exception pointer supports equality
but lacks the modern boolean conversion, so empty checks use equality.

## Verification boundary

Run `powershell -File tools/test_async_compat.ps1` from the repository root
(or use pwsh).
`-HostOnly` omits XDK compilation. The script locates MSVC with vswhere, compiles
with `/W4 /WX`, runs a hidden host test with a 30-second deadlock deadline, then
compiles the same implementation and complete test source to XDK objects. Logs
and binaries are confined to `tests/async-compat/out/`.

The suite covers eight blocked readers, broadcast publication, repeated access,
shared result identity/lifetime, exceptions surviving worker exit, abandonment
waking a reader, duplicate producer operations, null exception rejection,
move-only values, consumed future invalidation, failed value construction and
retry, mutex contention, destructor join, moved workers, manual event reset, and
100 competing-producer races. It instantiates both current ResourceManager result
shapes using a test resource object. No resource manager, archive loader, or pool
is mocked or declared integrated by these tests.

This suite covers host execution and XDK object compilation. It does not exercise
Xbox exception transport or the integrated resource manager. No standalone test
XEX is built; use the [integrated build](../../../../docs/XBOX360_BUILDING.md)
and target tests for those boundaries.
