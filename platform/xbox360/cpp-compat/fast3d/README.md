# Pinned Fast3D XDK compiler projection

`python tools/prepare_fast3d_xdk.py --compile` stages and compiles the complete
BattleShip `libultraship/src/fast/interpreter.cpp` and paired `Texture.cpp`.
`source-lock.json` checks original bytes; generated files retain original-line
mapping and mark changed spans with generated paths. No reference tree is edited.
The resulting objects and exact commands are in `scratch/fast3d-xdk`, with
`compile-audit.json` describing compilation only, not an application link or run.

The generator consumes the current canonical graphics, resource, binary-reader,
audio and configuration header projections. `staged-inputs.json` hashes those
inputs. Logging requires the actual `scratch/logging-xdk/core-include`,
`scratch/logging-xdk/include` and `upstream/dependencies/fmt-xdk` projections.
The complete original resource/context classes remain in the compiler tree.

The interpreter's algorithms, six opcode tables, Smash runtime display-list and
relocation calls, texture masks/extents, sprite and primitive-depth paths remain
the pinned source. Syntax changes preserve member initialization and partial
aggregate defaults, enum values, scoped if initializers, range lifetimes and
single evaluation of range ends. Full texture/combiner key fields remain intact.
The unused `Gui.h` transitive include becomes direct real logging/platform
includes. CVar compile definitions come from the hashlocked pinned CMake file.

The narrow library operations are:

- `views.h`: dynamic non-owning span/string view operations used by this source.
  Ordered heterogeneous lookup uses a linear comparison scan because the XDK
  map lacks transparent lookup. It retains view lifetime and allocation behavior.
- `atomic.h`: this source's relaxed integer load/store/compare-exchange, using
  native interlocked operations. Strong CAS is a valid implementation of weak
  CAS and updates the expected value on failure.
- `platform.h`: real `XboxEnv_Get` and snprintf dependencies, reserve via
  `rehash(ceil(count/max_load_factor))`, viewport rounding, and signed matrix-word
  rounding through SDK `__fctiw`/`__stfiwx` with the current FP rounding mode.
  The host test uses the equivalent SSE current-mode conversion instruction.
- The sole map `merge` consumes a local scalar depth-result map with no escaping
  source references or iterators. Range insertion preserves existing destination
  entries; the temporary is then destroyed at the same function exit. This is
  not a general node-transfer replacement.

The viewport rounding expression is the proven donor's
`D:/Projects/SoH360/platform/xbox360/math_platform.cpp:29`, narrowed to the actual
binary32-derived viewport input domain. Donor file SHA-256:
`4085d75c2b355bb3b2df207d6f6ad3e35c36ec49de03e41ca77c2cb7d31610a5`.
No donor checkout is needed to generate or build this projection.

The desktop low-address DLL exception is replaced by a bounded Xbox predicate.
SDK 21256.3 documentation, `doc/1033/xbox360sdk.chm`, topic
`dev_linker_images.htm` (Executable and DLL Images), mandates loaded image ranges
`0x82000000..0x8BFFFFFF` for 64-KB pages or `0x92000000..0x9BFFFFFF` for 4-KB
pages. Low preferred bases are remapped into those ranges. Both actual 32-bit
call sites query only `0..0x0FFFFFFF`, so no loaded XEX can qualify. The helper
rejects queries outside its audited domain with an exception. Exact registered
asset ranges remain unchanged. This requires neither XBDM nor an undocumented
kernel ABI, and is not a general module lookup function.

Validation commands:

```
python tests/fast3d-xdk/test_prepare.py
powershell -File tests/fast3d-xdk/run.ps1
powershell -File tests/fast3d-xdk/run-platform.ps1
powershell -File tests/fast3d-xdk/run-header-math.ps1
python tools/prepare_fast3d_xdk.py --compile
```

Checks cover non-owning lifetime/bounds behavior, atomic expected updates, every
opcode entry and its order, constructor defaults, full keys, actual matrix
routines, 4,096 actual current combiner mappings and identical diagnostics.
Platform tests compare 128,004 matrix-rounding cases across all four rounding
modes, viewport edge cases, reserve capacity and the scalar depth insertion.
Actual full headers, six tables, math bodies and helper tests also compile for
XDK. Target execution, physical rendering, complete resource/GUI integration and
application linking remain integration work; these tests do not claim them.

Failure-path corrections: Destroy closes its window backend only after that
backend has been assigned by Init. A failed texture-upload allocation throws
std::bad_alloc instead of allowing the first decode to write through null.
The original allocation size and decoding path remain unchanged. This does not
establish that the allocation succeeds on Xbox or make shutdown allocation-free.

RDP value-initialization: SDK 21256's emitted `new RDP()` allocates storage and
constructs the nested `RawTexMetadata` objects without first zeroing the enclosing
aggregate. This left mode bits, image addresses, grayscale, texture flags and
other scalar members indeterminate. The modern upstream expression zeroes them.
SoH's older Fast3D keeps RDP in static storage and does not expose this failure.
The single allocation is projected to `Fast::XboxValueInitializeRDP()` in
`rdp_value_init.h`: global operator new, zero raw storage before object lifetime,
then the real placement constructor, with allocation cleanup on an exception.
Normal `delete mRdp` remains the owner; no live shared_ptr is byte-cleared.
The build verifies this ordering and destination in the actual linked PPC image.
The actual-header differential test poisons allocation storage and checks all
RDP fields against upstream defaults, including nested scales and resource owners.
Evidence and the failing pre-fix binary: `scratch/evidence/rdp-value-init`.
