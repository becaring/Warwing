# Real application startup integration overlay

`tools/prepare_startup_xdk.py` reads seven SHA256-locked upstream files and writes
mapped copies under `scratch/startup-xdk/generated`. Original BattleShip and
libultraship sources remain unchanged. Generation is deterministic and rejects
source or exact-anchor drift before writing outputs. This target-only overlay
is not a replacement entry point, frontend, game loop or Context implementation.

The real `main -> PortInit -> PortGameInit -> PortPushFrame` chain remains in
`port/port.cpp`, including actual factory registration, controller/window/menu
construction, shader prewarming, 32 kHz audio settings, game coroutine ownership,
event registration and game-controlled shutdown. Normal teardown is actual
PortGameShutdown, PortShutdown/Context release, shader writer join/drain, then
native diagnostics shutdown. Exceptions also release any started game coroutine
before Context. PortInit failure releases its partially initialized Context;
the actual Context destructor checks window/config pointers before calling their
methods, retaining successful teardown order.

Before LUS workers, the native helper initializes the donor QPC frequency cache,
loads immutable `game:\smash360.env`, and validates logical cwd `game:\`. Missing
optional environment file is permitted; invalid, unreadable or repeated loading
fails startup. The donor's XContent device selector/container mount now supplies
`smashsave:\` for Context's writable app-data path (logs, configuration and SRAM).
Its mount and flush/close bodies are generated from the hash-locked SoH platform
source with only title/container names changed. Mounting occurs before LUS workers;
closing occurs after real Context teardown. BattleShip's normal file code remains.
The bundle path and logical cwd remain `game:\`; actual app_paths lookup retains
its app-data-then-bundle order. No UWP `E:/BattleShip` assumption is applied to XDK.
Port logging has the donor-style cache fallback and flushes startup diagnostics;
the actual rotating LUS logger remains in the mounted app-data directory.
App-relative native paths call the central filesystem `make_preferred()` before
reaching CRT consumers: Xenia kernel tracing proved mixed `\logs/BattleShip.log`
resolved incorrectly on reopen. This follows the donor's slash normalization;
the game-owned relative name and file contents do not change.

The Xbox path requires actual regular files for f3d.o2r and the region-selected
game archive. Missing files fail with an actionable diagnostic. The actual
ArchiveManager still opens and validates the archives; existence is not treated
as successful loading. Shader bootstrap no longer allows empty archives merely
to display the desktop first-run wizard. Desktop extraction/wizard, window icon,
Win32 crash/console APIs and RenderDoc calls are explicitly excluded for Xbox.
Game frame limit and optional source-reloc archive settings read immutable native
environment values. Shader prewarm timing uses the same imported QPC clock.

`gameloop.cpp`, `gui/PortMenu.cpp` and `enhancements/enhancements.h` here contain
**capability-only** changes: Discord, desktop updater, RenderDoc call sites and
the desktop open-folder widget are unavailable on Xbox, with no callable success
stubs. Compose these exact changes with their owners' syntax overlays before
production staging. Other desktop-only menu features, including shader downloads,
postprocess shader tools, multi-window settings and texture-authoring features,
still need their separate platform capability decisions; this overlay does not
silently disable them.

Canonical backend declarations and Config/Audio implementations live in
`scratch/config-xdk/generated`: FAST3D_XENOS=3/count4 and XAUDIO2=4. Actual native
Fast3dWindow/Gui backend construction is owned by graphics integration. The paired
Window.cpp constructor change there must accompany its header's initializer
lowering. No alternate Context or Window header is supplied here.

Run `python platform/xbox360/cpp-compat/startup/verify.py` for generation/lifecycle
source checks and XDK objects. The native startup helper, actual generated
app_paths.cpp and original port_log.c pass PowerPC object compilation. The combined
build uses the corrected port_log projection as C (`/TC`), with declarations moved
before statements and the centralized complete-string formatter. The first native
run reproduced InitLogging failure on the read-only game mount. Runtime verification
of the mounted app-data correction is pending.

`compile_closure.py` records an older isolated dependency probe. Its failures are
superseded by the complete canonical application composition, which compiles and
links actual Port.cpp and Context.cpp. See BRINGUP.md and the native build logs for
current execution evidence; no visible game output is yet proven.
