# Actual HiRes pack and hook on XDK

`python tools/prepare_hires_xdk.py --compile` generates the four pinned actual
`port/hires/HiResPack` and `HiResHook` sources/headers into the BattleShip-relative
overlay `scratch/hires-xdk/overlay`. Input SHA256 locks reject source drift;
manifest records support and staged-source hashes. Both complete production
translation units compile with the XDK. The C hook header remains C-compatible.

The actual filename grammar, decoded RGBA8 CRC keys, deterministic loose/ZIP
collision ordering, libzip/stb decoding, corrupt-member limits, shared-pointer
LRU and returned-texture pin, cache budget controls, workers with private ZIP
handles, atomic job counters, stop/join/reinitialization, CVars, registration,
miss dumps and PNG substitution are retained. HiRes is not disabled. The pinned
desktop defaults (including512MiB cache budget and up to4 preload workers) remain;
this projection does not establish those defaults fit an Xbox workload.

Compiler changes are nested namespaces, explicit member/aggregate constructors,
typed lambdas, scoped if-initializers, pair/range lowering, equivalent map/list
insertions, and named callback/table-builder functions where old MSVC rejects
captureless-lambda conversion or crashes on a returned std::array. Mutex/thread
operations use existing async primitives. Optional and string_view use central
projections. Central string_view adds allocation-free rfind(char) and
find_last_of(view); central port atomics add unsigned, fetch_sub and acq_rel.
Interlocked operations retain full native fences; subtraction negates in unsigned
arithmetic so signed minimum does not invoke undefined signed overflow.

The source dump had a real endian dependency: fwrite(DumpHeader) wrote the native
representation of seven uint32 fields, fmt/siz and six padding bytes. The pinned
desktop writer/comment defines magic0x44524853 as little-endian SHRD and asserts
size36. The new EncodeDumpHeader/WriteDumpHeader explicitly serialize those same
36 bytes in little-endian on either host. Texel rows/palette bytes are copied
unchanged. The BMP hook writer already serializes LE explicitly and is retained.
The referenced unbundled tools/hires-pack-convert/convert.py is absent; the format
contract is verified against the actual desktop writer, not an external converter.
MaybeDumpSource remains dormant in the current hook, as documented upstream.

`python tests/hires-xdk/run.py` builds/runs the complete original and projected
HiResPack.cpp with actual libzip/stb/filesystem/thread implementations. Test-only
providers supply application path, CVars and logging; no production replacement
Context is introduced. Fixtures exercise valid/invalid filenames, CRC32, LRU
eviction and live pins, loose+ZIP collision winner, corrupt PNG removal, preload
completion/join, repeated initialization, and dump row-stride/palette output.
Original and projected dump files equal the explicit36-byte LE expected record.
String-view comparisons include empty ranges, boundary positions and embedded NUL.

`python tests/port-xdk/run_tests.py` additionally passes the extended unsigned
counter/acq_rel decrement, modulo wrap and signed-minimum subtraction assertions,
alongside existing100000 concurrent increments and native reservation/fence checks.
The actual pack and hook compile to PowerPC objects; host tests do not prove native
thread execution, physical filesystem behavior, GPU substitution, memory budget,
final application linkage, or Xbox/Xenia runtime behavior.
