# Actual Context and C bridge XDK closure

`python tools/prepare_context_xdk.py --compile` composes the exact hashed startup
Context overlay before compiler changes. It emits a sparse source/header overlay
at `scratch/context-xdk/overlay`, a compiler mirror, per-source command/log files,
and input/support/output hashes. Original/reference sources remain read-only.

All 14 actual production translation units compile to XDK objects: Context,
CrashHandler, FileDropMgr, EventSystem, luslog, stox, and the console
variable/controller/window/event/crash/debugger/graphics/resource C bridges.
Console and other GUI classes, audio and resource implementations, controller classes, and general
utility implementations retain their separate owners. The generated headers
include real complete dependency types where current Context.h now forward
declares them; no substitute application classes are defined.

The authoritative startup overlay supplies game:\ paths, actual filesystem
joining, null guards on partial Context teardown, and removal of unsupported
desktop dialogs/console allocation. The original Context Init sequence and all
real service calls remain. Logging retains queue 8192/one worker/block, configured
severity, source location, 10 MiB/ten-backup rotating sink, registration/default
logger and final shutdown. Its release and debug choices remain distinct.
Xbox teardown now stops the real mapped rumble outputs and all four native
physical motors before destroying the ControlDeck, including outputs whose
mapping was removed while rumble remained active.

Language lowering moves EventSystem/FileDropMgr/CrashHandler field initialization
into constructors, changes typed aggregates to named locals, expands the actual
EventListener struct binding, and preserves range lifetime/reference behavior.
The gfx bridge receives its missing std:: qualifier. luslog explicitly chooses
the current preformatted string_view overload so arbitrary braces remain literal;
its existing 4096-byte printf wrapper/truncation is retained. stox uses actual SDK
string conversions and existing fallback behavior unchanged.

Desktop DbgHelp, x86 register formatting and SetUnhandledExceptionFilter are
excluded on Xbox; native unhandled PPC exception interception/stack capture is
not implemented. The real CrashHandler object, buffer, callback registration and
explicit PrintCommon diagnostics remain. Desktop file-drop duplicate-handler
symbol lookup becomes an actual address diagnostic on Xbox; handler dispatch and
notifications remain. No native OS drag/drop event producer is claimed.

The original CrashHandler callback constructor invokes a temporary default
CrashHandler rather than initializing its own buffer; this existing behavior is
preserved and is not the Context startup path (which uses the default constructor).
General existing crash-buffer bounds behavior and lusprintf's absent va_end are
not repaired by this compiler projection. They require separate source fixes.

`python tests/context-xdk/run.py` compares original and projected EventSystem and
C logging against actual current spdlog. It verifies event priority ordering,
duplicate rejection, unregister behavior, caller metadata (actual pointer keys),
source locations, literal braces/percent characters, printf formatting and buffer
truncation. All 14 whole translation units compile with the XDK. This is neither
a host-linked whole Context test nor final application linkage or Xbox execution.

The native initialization projection now removes the published window if its
Init throws, then rethrows the original error. Publishing during Init is required
by GUI initialization; retaining a failed window let Context shutdown query a
missing backend while saving dimensions. The interpreter projection separately
allows destruction before Init assigns its window backend. Normal startup and
frame order are unchanged. These corrections are source-reviewed failure paths;
target allocation-failure injection remains unvalidated.
