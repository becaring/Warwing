# Xbox environment lookup

XDK excludes desktop `getenv`. Shipyard's `sources/environment/launch_environment.h` owns the bounded reader,
parser and immutable lookup. `environment.cpp` maps that service to the
`XboxEnv_*` ABI. File reading follows the SoH360 `platform.cpp::ReadPath`
CreateFile/GetFileSize/ReadFile/CloseHandle pattern.

The application must call `XboxEnv_LoadFromFile("game:\\smash360.env")` once
before PortInit or any worker. `Smash360Startup::Initialize` now performs this
call on the application startup path.
`XBOX_ENV_ABSENT` is normal: no variables are set. Other errors must be logged
and surfaced during startup. The file is optional; nothing enables diagnostic
flags, advances menus, limits frames, or changes game defaults automatically.

Format: ASCII variable names `[A-Za-z_][A-Za-z0-9_]*`, `=`, then literal value.
LF and CRLF work. Empty/whitespace-only lines and lines beginning with `#`
after optional whitespace are ignored. Values are not trimmed or expanded;
quotes and `#` in values are literal. Duplicate names, embedded NULs, malformed
lines and files over 1 MiB are rejected. Errors never publish a partial table.

After successful initialization (including absent file), reload is rejected.
Concurrent lookups are read-only; initialization must finish before starting
workers. Returned pointers have process lifetime and must not be modified,
matching getenv's usage contract. Names are case-sensitive. Unknown names
return NULL. No setenv/putenv consumer is currently part of this adaptation.

`tools/test_environment.ps1` executes the shared parser/lookup through the
Smash adapter on host Windows and compiles the adapter with XDK.
See [development](../../docs/DEVELOPMENT.md) for integration verification scope.
