# Xbox runtime adapter

`storage_adapter.cpp` supplies Smash360's container policy to the directly
compiled Shipyard selector: user 0, 1 MiB request, `smashsave` mount,
`Smash360` container, and `BattleShip` display name. The adapter owns the
mounted state and serializes open/close. Shipyard owns XAM notifications,
startup presentation, same-profile retry, XContent open, flush, and close.

The selector must initialize the native display before XShow and continue
presenting while the overlapped request is pending. XAM retains the overlapped
and device-output pointers until completion, including after cancellation.
One retry is allowed only when a pending cancellation overlapped a sign-in
notification and the stable offline profile remains unchanged. A visible UI,
observed B, changed profile, missing identity, or presentation error vetoes it.

`diagnostics_adapter.cpp` owns Smash's formatting, debugger/file output,
worker placement, and main-thread console delivery. It compiles the direct
Shipyard `sources/diagnostics/queue.cpp` for owned records, bounded backlog,
backpressure, synchronous fallback, drain, and shutdown. The diagnostic writer
targets `game:` and is not the game's save-data implementation.
`prepare_runtime_xdk.py` compiles these two direct sources and records hashes;
it emits no source. The shader worker joins before `Smash360_CloseAppStorage`.

The shared host selector contract covers both active consumer policies. XDK
compilation and Xenia are separate gates; the existing Smash hardware receipt
validates the same-profile recovery sequence on one console, not every XAM
failure mode.
