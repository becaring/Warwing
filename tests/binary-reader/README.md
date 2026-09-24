# Actual LUS binary-reader XDK slice

Run from any working directory:

```powershell
python D:\Projects\Smash360\tools\prepare_binary_reader_xdk.py
python D:\Projects\Smash360\tests\binary-reader\test_generation.py
python D:\Projects\Smash360\tests\binary-reader\run.py
```

The host test needs the local VS2022 14.43.34808 compiler/CRT, Windows SDK
10.0.26100.0, and the already extracted `scratch/assets/BattleShip.o2r`. Native
compilation uses the installed Xbox 360 SDK PowerPC compiler. Host and Xbox
outputs stay below `scratch/binary-reader-xdk`; no test XEX is created.

The generator reads seven SHA-256-locked upstream files. It preserves their
algorithms and source-line mappings, producing standalone generated include/src
trees and a manifest. Only exact anchored edits are allowed; validation and
transformation of all inputs complete before output writes. The manifest records
all input/output hashes, the generator/helper hashes, and the pinned LUS commit.

Changes are scoped enum representations, explicit field initialization in all
BinaryReader constructors, expanded MemoryStream delegation, removal of final/
override/defaulted-destructor syntax, and centralized zeroed allocation / NaN
operations. Both native-endian conditions recognize `_XBOX && _M_PPC`. No
decomp layout or bitfield declarations are touched. The generated enum wrappers
cover the reader's reached construction/comparison operations with int-width
storage and no implicit class-to-integer conversion; they are not a general
language-level implementation of every scoped-enum expression (e.g. arbitrary
explicit casts from the wrapper need a centralized GetValue-based lowering).

The MemoryStream delegation lowering copies the exact original default body
ahead of each original delegating-constructor body, including its initial empty
vector allocation. Host differential allocation counts prove those effects are
retained. Existing seek/write/Close behavior is intentionally retained, including
End seek's `mBufferSize - 1 - offset` convention. `new char[length]()` preserves
the original make_unique array's value initialization.

Tests compile the actual original production sources and the generated copies,
then compare their complete output. Cases cover signed/unsigned integer widths,
tagged LE/BE float and double, infinity, signed zero, NaN exception text, all
reader construction paths' native default, buffer-copy versus shared ownership,
shared offset/lifetime, owned reads, writes, seeks, Close and ToVector. A real
RELO entry with external dependencies is extracted from BattleShip.o2r; its
metadata and untouched payload hash must agree with independent Python decoding.
Fixture provenance is recorded in `fixtures/provenance.json`.

The helper test checks array zero initialization and scoped type separation.
The XDK contract object checks native Big selection, IS_BIGENDIAN, 32-bit
pointers and int-width enum storage. Three production objects plus this compile
contract must have the PowerPC-BE COFF machine field 0x1f2. The runner records the
command, object hashes and comparison output in `verification.json`.

This proves host behavior agreement and XDK compilation of this slice. It does
not establish Xbox runtime execution, final application linking, or visible boot.
# Writer extension

`python tests/binary-reader/run_writer.py` compares the actual original and
projected BinaryWriter bytes for all three constructors and both explicit byte
orders. Independent Python encoding also checks signed/unsigned integers,
floating point, negative zero, infinity, embedded-NUL strings, paired integers
and raw bytes. The production writer and contract compile with XDK; this is
not target execution. Constructor defaults and the string range loop are the
only writer source transformations.
