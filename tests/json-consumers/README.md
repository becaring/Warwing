# Real JSON consumer comparisons

Run `run.ps1 -Consumer config`, `-Consumer cvar`, or `-Consumer resource` from
this directory or the repository root. Repeat with
`-Label adapted -JsonInclude <shipyard>/sources/json/include`
and `-JsonSource <shipyard>/sources/json/json.cpp`.
The script builds the actual unmodified consumer implementation with VS2022,
once against official nlohmann 3.12 and once against the Xbox compiler backend.
Objects have unique names, including the case-insensitive Json.cpp/json.cpp pair.

Config tests use real persistence and type/error behavior. CVars tests invoke
real ConsoleVariable plus Config. Resource tests invoke real ResourceLoader,
BinaryReader/MemoryStream, JsonFactory and resource types. They exercise metadata
dispatch, comments, numeric types, ownership and propagated parse/type failures.
Compare the generated settings.json files byte-for-byte. Config's inherited
missing dotted-path Contains behavior is preserved, not silently repaired.

Context/window/manager dependency fixtures are explicitly test-only. Unexpected
window or archive calls throw. These tests do not initialize the application,
read an O2R archive, exercise resource cache concurrency, compile all consumers
on XDK, or prove a native boot. No fixture belongs in the application manifest.
