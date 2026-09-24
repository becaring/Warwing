# Xbox endian overlay

`python tools/prepare_endian_xdk.py` produces a sparse overlay at
`scratch/endian-xdk/source`. Original BattleShip remains read-only. Prepend the
overlay root, `decomp/include`, and `decomp/src` to include search paths **before
preprocessing**, and select its source file when present. The game compile tool
supports `--source-overlay scratch/endian-xdk/source`.

`source-lock.json` pins the nine exact source files. Preparation validates every
SHA256 and match count before writing any output, rejects source/output overlap,
and records source/output/helper hashes and edits in `endian-manifest.json`.
Line-preserving edits plus original `#line` paths retain diagnostic mapping;
the added WP conditional has its own explicit line reset. Source drift is an
error, not an invitation to silently regenerate the lock.

The platform predicate is `_XBOX && _M_PPC` (or actual compiler BE macros), matching
the separately owned LUS generated endianness detection. Neither `PORT` nor
`_MSC_VER` alone means little endian. General LUS BSWAP primitives and the real
header-driven BinaryReader are not changed here.

Implemented transformations:

- Select native BE decomp declarations while retaining PORT token representations.
  Mask BITFIELD_SEXT input to its width before sign extension: PORT consumers
  otherwise sign-extend already-signed BE fields twice (-1 becomes -257 at width8).
- Correct both the `du` word order and `DU_INIT` initializer through the same
  host-endian predicate. This preserves the original double union implementation.
- Make the audited reloc module's LE word/halfword repair helpers identity on BE;
  bypass its blanket conversion/scan on BE; preserve mixed-byte structs and
  non-destructive FT texture-part snapshots. Keep every token operation, registry,
  range protection, eviction, synthetic-sprite marking and semantic deswizzle.
- Disable figatree halfswap **and halfswapped-range registration** on BE, including
  the force override path. This prevents downstream AObj32/spline repair from
  touching data that never needed conversion.
- Keep particle bank validation/cache/pointerization and make only the header-field
  byte reversals conditional. Convert particle bytecode floats and the audio
  envelope float loop through an alignment-safe BE-to-native byte copy. Audio
  parsing/allocation and raw ADPCM/sequence bytes remain the original code.
- In sys/audio.c, reverse the 16 sequence track offsets and division word only
  on LE hosts. The raw SBK already contains BE words. The original unconditional
  desktop reversal crashes n_alCSeqNew on Xenon (OpeningRoom BGM33 track offset
  0x101D becomes 0x1D100000). Preserve the sequence copy, all player state changes
  and byte-oriented MIDI event stream. All 47 real SBK headers are checked under
  both scalar-load policies; the original code fails the BE case.
- In WPAttributes, suppress the original `angle:10` only under PORT. PORT already
  has `_angle_raw` at0x26 and wpmanager reads it directly; adding the original angle
  again when enabling the BE branch duplicates its storage. Keep the original
  sizeof(WPAttributes)==0x34 assertion and all other fields.

Validation commands (from Smash360):

```
python tools/prepare_endian_xdk.py
python -m unittest discover -s tests/endian -v
python tests/endian/run_helpers.py
python tests/endian/run_xdk_probes.py
```

Host helper tests extract the actual generated conversion/deswizzle functions;
test scaffolding supplies only token lookup and disabled diagnostics. They verify
both LE and simulated BE byte policies against the real archive's first FGM
struct (floats100,190,-200) and particle count119. They cover unsigned/already-signed
bitfields, vertex/struct/palette identity, non-destructive containers, figatree
classification, sprite deswizzle at4/8/16/32bpp, 4c post-decode, idempotence,
heap reuse, and synthetic sprites. This is **host byte-policy evidence**, not
execution of BE native scalar loads or the complete resource runtime.

The XDK test compiles exact selected declarations using generated config/du/WP
code. It parses COFF symbol bytes and checks native DU_INIT==1.0, sign-extension
constants, sizes2/4/2/4 for AObj16/AObj32/FTKey/FTMotionAttack, WPAttributes size52,
and PowerPC accessors: opcodes shift25/11/12, WP scale loads0x28 then shift22,
damage reads0x28 bits21:14, angle loads0x26 then signed shift6. These tests first
failed for the original WP duplication and signed-extension behavior. Outputs
are in `tests/endian/out`; compiler failures are retained in logs.

Remaining boundaries:

- This is not an all-struct IDO/XDK ABI proof. Remaining mixed/zero-width bitfields,
  all positional initializers and ROM overlay types need actual compiled checks.
  Do not remove static layout assertions or introduce global packing flags.
- Full bridge translation units still need the C++ compatibility layer, integrated
  compiler validation and runtime archive ownership tests. Extracted helper tests
  are not a linked bridge or alternate resource implementation.
- LUS Native/header-reader adaptation is separately generated. Both overlays must
  be in the final build; fixing decomp alone cannot load LE archive metadata on BE.
- The Xbox GPU upload/readback byte order and final PCM sink remain separate
  platform boundaries. No Xbox/Xenia boot, frame, audio or hardware claim follows.
