# Actual Config/ConsoleVariable compilation slice

`tools/prepare_config_xdk.py` generates source-mapped, SHA-locked copies of the
real pinned Config, ConsoleVariable, StringHelper, Audio and the needed declarations.
It does not supply substitute Config, CVar, Context or Window classes.

The generated include root is `scratch/config-xdk/generated/include`. Reuse the
actual audio lowering at `scratch/audio-xdk/generated/include`, the explicit
JSON backend, and native filesystem. Current real logging remains required.
Use `scratch/logging-xdk/core-include` before `scratch/logging-xdk/include`,
then the real fmt4 compiler-boundary include root.

The reviewed audio integration patch is applied with its SHA256 and every hunk
context checked by `audio_integration.py`. The canonical AudioBackend includes
XAUDIO2=4; the real Audio class selects and constructs XAudio2AudioPlayer on Xbox,
persists its name through real Config, and fails on unsupported/failed native
initialization. It does not report success through a null player. The actual
stereo mixer supports stereo and matrix 5.1 output; raw 5.1 input remains unavailable.
WindowBackend keeps existing IDs 0..2, adds FAST3D_XENOS=3 and sets count=4;
Config's actual getter fallback and persisted name match. Fast3dWindow's backend
construction belongs to the separate graphics integration.

## Transformations

- The original Config/CVar function bodies retain all decisions and persistence
  operations. Range-for is lowered by `lowering.py`, a reusable AST operation
  derived from the donor and the existing Prism cached-end correction. It keeps
  `auto&&` lifetime, cv/ref binding, begin/end evaluation count, break and continue.
  Unknown initializer-list and structured-binding ranges are rejected.
- The two actual Config structured bindings are lowered explicitly. Map insertion
  uses XDK's `insert(make_pair(...))`, with the same inserted boolean. Its C++17
  if-initializer becomes a local declaration in the same function scope.
- Actual enum declarations become typed wrappers retaining enum names, values and
  integer-sized storage; switches/casts at the audited callers explicitly use the
  underlying value. AudioChannelsSetting remains its original ordinary enum.
- CVar's default union member becomes an explicit constructor; current reached
  value-initialized CVar has Integer/zero type and null String as before.
- string_view becomes a non-owning pointer/length boundary type with the actually
  used find/substr/iteration/equality operations. CVar hashing is allocation-free
  and matches the target STL's string hash; unknown methods are absent. Old XDK
  unordered_map uses its ordinary key-converting lookup rather than modern
  heterogeneous lookup, so allocation/performance of char* lookup can differ.
- The actual StringHelper source is retained. Its equal-with-two-ranges operation
  becomes an explicit size check followed by the supported predicate overload;
  strtoull binds to the XDK CRT spelling. Its other inherited behavior remains.
- Filesystem headers/namespace bind to the shared native filesystem. Stream opens
  explicitly resolve absolute paths before passing narrow names to XDK fstreams,
  so they follow the same logical working directory as filesystem metadata calls.
  Startup must initialize the filesystem working directory before relative paths.
- Real Window's Gui/GuiWindow/MouseStateManager shared-pointer dependencies become
  proper forward declarations. The full Window declaration and members remain.
  Its mLastScancode initializer is relocated to the real primary constructor in
  the paired generated Window.cpp. **Use that paired source patch if compiling
  Window later**; full Window implementation lowering is outside this slice.
- Context's default argument/value-construction syntax is lowered, retaining its
  actual methods and members. Its spdlog dependency is not stubbed. DISABLE_SCRIPTING
  is the current runtime target flag; the inactive scripting declarations have
  not been downleveled here.

## Verification and current boundary

```
python tools/prepare_config_xdk.py
python tests/config-xdk/test_generation.py
python tests/config-xdk/run.py
python tests/config-xdk/compile.py
```

Host tests use original production consumer bodies versus the generated ones,
with the same JSON backend, and require identical saved bytes. The original
Config/CVar public consumer fixtures are supplied by
`tests/json-consumers`; their Context/window definitions are explicitly test-only.
No fixture is in a production source manifest. Legacy migration additionally
exercises actual DiskFile/Path/Directory/StringHelper and file removal solely on
its own generated test fixture. The inherited CRLF-string carriage return is
preserved, not repaired during compiler adaptation.

Five generation/range invariants pass. The helper lifetime/hash contract passes
original/generated host tests and compiles with XDK. Actual generated Config.cpp,
ConsoleVariable.cpp, StringHelper.cpp and Audio.cpp compile to PowerPC objects
using the actual current spdlog header adaptation. The original/generated host
Config, CVar and legacy migration suites pass with identical persisted bytes.
`scratch/config-xdk/native-verification.json` records the actual compiler result;
`host-verification.json` records the three output hashes. No production logging,
Context or Window replacement is used to obtain these objects.

No complete application link, Window lifecycle, Xbox execution or boot is claimed.
