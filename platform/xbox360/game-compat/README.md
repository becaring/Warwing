# BattleShip C compilation audit

This directory supports compilation of the pinned BattleShip C translation
units with the native Xbox 360 XDK C compiler. It supplies no game functions,
game globals, scheduler replacement, application entry point, or XEX.

Run from `D:/Projects/Smash360` using Python 3.13:

```powershell
python -m pip install --target scratch/game-xdk/python-tools tree-sitter==0.25.2 tree-sitter-c==0.24.1
python tools/game_source_manifest.py
python platform/xbox360/game-compat/verify.py
python platform/xbox360/game-compat/verify_bool.py
python platform/xbox360/game-compat/verify_narrow.py
python tools/prepare_endian_xdk.py
python tools/prepare_crt_xdk.py
python tools/prepare_game_xdk.py --source-overlay scratch/endian-xdk/source --generated-include scratch/generated/include --generated-include scratch/generated/decomp/src --keep-going --archive
```

`XEDK` defaults to `C:/Program Files (x86)/Microsoft Xbox 360 SDK`.
The host verification fixture uses VS2022 Community's `vcvars64.bat`; override
its location with `SMASH_HOST_VCVARS`. Root-owned `tools/prepare_assets.py`
generates the reloc and credits inputs. This tool does not generate or replace
missing resources.

`--source-overlay` accepts sparse upstream-relative overlays before XDK
preprocessing and may be repeated. Conflicting replacements for one file are
rejected; compose those transformations explicitly before staging. The driver
builds `scratch/game-xdk/compile-tree` so quoted sibling includes cannot bypass
an overlay through the original header's directory. The audit hashes every
overlay input and records original/input/generated hashes for the complete
source/header mirror in `staged-inputs.json`. The endian transformations and
their separate native-layout checks are documented by that overlay's owner.

The staging API is reusable by C++ integration:

```python
from source_tree import stage_sources
records = stage_sources(upstream_root, generated_root,
                        translation_units=["port/port.cpp"],
                        overlays=[endian_overlay, other_overlay])
```

Load that module from `platform/xbox360/game-compat`. Paths in
`translation_units` and optional `extra` are relative to the upstream root.
The mirror includes the selected translation units and header/include
fragments from the audited include roots, plus explicit overlay sources; it
does not copy repositories, binaries, archives, or ROM assets. Literal quoted
and angle includes are followed within the upstream source roots (including
the real `ft/ftcollision.txt` code fragment). Initial unconditional pragma-once
directives precede generated #line mappings because XDK identifies pragma-once
headers using the logical filename. Unchanged
files receive original-path `#line` mappings. A generated-file index permits
removal of obsolete mirror files without deleting unrelated directories.
Overlay providers retain responsibility for their own original-path mappings.

The source manifest contains 486 C translation units for the pinned US tree:
the exact `ssb64_game` directory globs and explicit libultra/audio lists, C
stubs, executable port C sources, and debug trace C sources. It excludes
`.inc.c` include files, debug game/overlay directories and unselected libultra
implementations. CMake's own evaluator independently reproduces the selected
set in `scratch/game-xdk/verification/cmake-sources.txt`. An upstream CMake hash
change stops generation and requires a source-selection review.

`--source` accepts exact manifest paths for targeted probes. `--audit-name`
chooses a report basename; generated source/object/log paths are shared, so
run the full audit last when retaining final evidence. Every report records
the original source, all preprocessor-discovered input hashes, compiler and
transformer hashes, commands, generated source and object hashes, and exit
codes. XDK `#line` directives remain in the generated C. No command modifies
the upstream tree. A failed source remains failed and is never excluded from
the game selection. A requested archive is withheld unless all 486 TUs pass;
even a complete C archive would still require the real C++ port/LUS platform
integration and linking.

## Compatibility boundary

The native sprite failure exposed an XDK packet-layout incompatibility:
`Gpopmtx` mixed `int` and `unsigned char` bitfields, and `Gsetcolor` mixed an
`int` bitfield with byte fields. XDK expanded each to 12 bytes, making the
game's `Gfx` union 16 bytes while Fast3D's `F3DGfx` remained 8. Live command
traces showed padding interpreted as NOOPs and texture rectangles consuming
the wrong continuation words. The hash-locked GBI projection makes the pop
parameter an `unsigned int` bitfield in its original word and the color opcode
an ordinary byte, preserving their intended N64 positions. A production PPC
assertion requires 8-byte Gfx packets. The XDK regression checks structure
sizes and three independently encoded contiguous texture-rectangle packets;
host tests retain the original command and cursor semantics. Evidence is in
`scratch/evidence/user-recording/gbi-*`. All 486 game C translation units
rebuilt, the XEX/link audits passed, and the user's post-fix recording verifies
original menu lettering, HUD sprites, stage-clear results and two gameplay
stages through the real Fast3D/Xenos path.

- Both active game generators import Shipyard's physical
  `python/xbox360_platform/c89_lower.py`. The BattleShip driver retains its
  own source manifest and selects `/upstream/` C spans; the shared lowerer
  owns scope conversion. `donor/provenance.json` records the historical donor
  hashes. The parser dependencies can be installed with the pinned command
  above.
- `inline` becomes XDK `__inline`; C11 `_Static_assert` becomes a unique
  negative-array-size assertion. Upstream Bitmap, Sprite and audio freelist
  layout checks remain active. An intentionally false pointer-width assertion
  must fail; positive ILP32/64-bit-integer assertions must compile.
- The exact numeric token `3.40282346639e+38F` becomes XDK's
  `3.402823466e+38F`. The original decimal is slightly above the exact maximum
  and XDK rejects it before IEEE rounding. Host execution verifies both
  spellings give `0x7f7fffff`; direct PowerPC COFF inspection verifies XDK emits
  `7f7fffff` and `ff7fffff` for positive and negative values. Strings, character
  literals and source line counts remain intact.
- `getenv` calls resolve to the explicit `char *XboxEnv_Get(const char *)`
  platform contract. No value is fabricated here. The platform implementation
  must supply configuration lookup, absence behavior and returned-pointer
  lifetime; object compilation is not evidence that the link dependency exists.
- The single `f32 __libm_qnan_f = NAN` definition in hash-locked
  `port/stubs/libc_compat.c` becomes an extern declaration. Root's
  `platform/xbox360/math_constants.cpp` supplies the actual canonical quiet NaN
  using the authoritative donor FloatBits initialization. The game SGI sin/cos
  functions remain selected and retain their real NaN dependency.
- `typed_generic.py` resolves only the exact `PORT_TOKEN_VALUE` association
  list using actual typedefs, struct members, lexical scopes, indexed objects,
  dereferences, casts, equal-typed conditionals and declared function results.
  It selects the existing `portRefGfxToken`, `portRefDObjDLLinkToken` or
  `portRefU32Token` helper. No casts are introduced. The XDK compiler then
  verifies the actual argument against that helper's typed parameter. Unknown
  expression types remain `_Generic` and are reported as compile blockers.
  The original and lowered host fixture deliberately give distinct results
  for the two same-layout struct types and verify exactly-once side effects.
- Only the named `opcode`/`param` rows of `GMRumbleEventDefault` tables receive
  positional initializer lowering, using the actual preprocessed field order.
  Added/missing/duplicate fields are rejected. Host execution checks field
  values before/after; XDK COFF inspection checks emitted bitfield bytes for
  both possible declaration orders. No struct declaration changes occur here.
- A hash-locked generated `PR/gbi.h` uses SoH360's active `CALL_2` macro-rescan
  pattern (namespaced as `SMASH360_GBI_APPLY`) for the dynamic and static
  combine-mode macros. It preserves the existing LERP implementations. Tests
  compare both native command words with explicit LERP calls, and host
  execution checks original/rescan versions and `pkt++` evaluation counts.
- `semantic_bool.py` handles the closed C bool surface: scalar declarations,
  initialization, simple assignment, casts and returns plus the exact actual
  `IEvent.Cancelled` and `WindowFocusEvent.Focused` members. Each written or
  returned value becomes `!!(expression)`, preserving single evaluation and
  C truth conversion before one-byte storage. It rejects bool arrays, pointers,
  parameters, aliases, increment/compound stores, escaping field/scalar
  addresses and unknown field/type shapes. This is not a `bool` byte typedef.
  Native C++ and lowered C compile to identical PowerPC instructions for bool
  returns, external bool calls and event byte loads/stores. The actual headers
  produce IEvent size1, FighterParentKindResolveEvent size12/offsets0,4,8,
  WindowFocusEvent size2/Focused offset1. Host original/lowered checks cover
  256/512, negative, fractional, NaN and pointer truth values, cast/return
  conversion and shadowing. The native C++ alternative was probed but rejected
  for general game compilation because C pointer/callback conversions differ;
  the production C driver remains `/TC` throughout.
- `narrow_c.py` uses actual GRKind enumerators and the Vec3f positions array
  shape to expand only the three map array designators, explicitly zeroing
  slots9-12/15 that C originally initializes implicitly. The source is hash
  locked; tests extract actual enum/vector/table declarations, execute original
  and lowered versions and inspect native PowerPC float bytes. Two hash-locked
  scmanager `__typeof__(gSCManagerTransferBattleState)` declarations become the
  verified actual `SCBattleState` type, without changing either global.
- The compatibility `intrin.h` declares XDK's native `_ReturnAddress` intrinsic;
  PowerPC assembly verifies `mflr r3`, with no helper call or implementation.
  Unimplemented platform APIs remain link dependencies. `/W3` is enabled so
  successful object compilation does not hide implicit declarations or other
  ABI-sensitive warnings.
- The hash-locked generated stdarg header uses XDK's actual `_crt_va_start`,
  `_crt_va_arg`, `_crt_va_end`, and pointer-cursor va_copy. Desktop upstream
  uses nonexistent `__crt_va_*` on XDK, which previously produced implicit
  function calls and uninitialized cursors despite compiling. A mixed
  int/int64/double variadic fixture emits identical PowerPC instructions with
  the generated header and with the native SDK header. This sparse header
  overlay is available at `scratch/game-xdk/c-language-overlay` for C++ staging.

Verification executes the original and lowered declaration fixture on the
host, covering initializer side effects, shadowing, nested for loops,
continue/break, and goto past an initializer. A separate native compiler
fixture first demonstrates sparse quoted-sibling override failure, then
verifies the mirrored header succeeds without modifying the original. The
XDK checks produce objects only. Neither these checks nor successful game object compilation prove
Xbox execution, coroutine behavior, rendering, complete endian correctness or
boot. Upstream `config.h` and `PR/guint.h` contain desktop endian assumptions;
the final command applies the separately audited endian overlay rather than
adding a blanket compiler define here.
