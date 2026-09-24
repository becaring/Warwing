# Current resource and archive source closure

`tools/prepare_resources_xdk.py` generates the pinned **actual** LUS resource
classes and implementations under `scratch/resources-xdk/generated/{include,src}`.
Original files remain unchanged. `sources.lock.json` rejects source drift and
the central mapped writer retains original `#line` provenance. The output keeps
ResourceManager, ResourceLoader, ArchiveManager, Archive, FolderArchive, O2rArchive,
their cache keys, virtual factories, JSON/XML readers and BS task queue. It is not
a substitute resource manager, synchronous loading facade, or donor package format.

## Composed compiler inputs

Use `tests/resources-xdk/compile.py` for the exact include order. The canonical
resource include root is `scratch/resources-xdk/generated/include`. It composes
the actual Config/Context/StringHelper declaration overlay, actual Audio header,
binary-reader overlay, value-types variant, BS 4.1.0 generated pool, native async
and filesystem primitives, current JSON backend and current generated spdlog
headers. The resource generator does not define a fake Context or logger.

The generated resource sources are paired with their headers: constructor
defaults and IResource's static `alt/` prefix were relocated, not removed. The
scoped-enum/variant/future/mutex namespace conversions are explicit. Range-for,
structured bindings, designated initializers, inherited constructors, contains,
starts_with and fixed constexpr uses are lowered only in hashlocked call sites.
The actual FolderArchive file helpers resolve stream paths through the explicit
filesystem cwd before opening them. `glob.h` supplies a one-byte C boolean only
for the Xbox C compiler; C++ keeps its built-in bool. CRC64 and glob algorithms
remain the actual LUS source.

`ResourceManager.cpp` no longer includes unused Context, ConsoleVariable and
StringHelper headers. Archive/O2r sources explicitly include the actual
ResourceManager declaration instead of depending on Window's incidental GUI
include graph. These changes reduce includes, not classes or runtime behavior.

## Explicit correctness changes

The generator keeps `corrections()` separate from syntax lowering and lists the
following authorized deviations in its manifest:

* Missing-resource cache writes hold the real mutex. Unload lookup/erase is one
  locked operation, reports the erased count, and retains the removed resource
  until after unlock so its destructor can reenter the resource system.
* ResourceManager drains and resets the real BS pool while its mutex and cache
  are alive. This fixes member destruction ordering for outstanding workers.
* A batch already executing on a pool with exactly one worker calls the same
  LoadResourceProcess directly for its children. The public async call is still
  queued on the real worker; with more workers it retains the original nested
  highest-priority submissions. Original one-worker code blocks behind itself.
* ArchiveManager's missing-file lookups use find/end rather than inserting null
  entries through operator[]. Concurrent missing loads therefore do not mutate
  the otherwise stable archive map. Concurrent archive mount/write operations
  still require external serialization; no general archive transaction lock is
  claimed.
* FolderArchive stores its base prefix with generic separators, matching the
  enumeration strings. The original Windows absolute-path backslashes made its
  unchecked Split(...)[1] invalid; the original integration attempt failed with
  bad_alloc. Normalizing this one prefix preserves file names and indexing.
* O2rArchive initializes its handle, closes an open entry through RAII if
  allocation throws, rejects sizes that cannot fit size_t and short/error reads,
  and performs an EOF read to force libzip's deferred CRC/size validation before
  marking a File loaded. It validates entry close. Failed write/discard clears
  the archive handle; a destructor discards a handle if close could not commit.

The actual startup call at `port/port.cpp:895` reserves zero resource threads.
XDK `winnt.h:2931` defines `MAXIMUM_PROCESSORS` as six logical threads; the native
hardware_concurrency helper uses that SDK constant. The real ResourceManager
subtracts its extra logging thread, giving five resource workers at startup.
Its ordinary default reservation gives four. This does not conceal the separately
tested one-worker case by forcing additional workers.

## Real ZIP dependency and remaining native boundary

The pinned LUS android/ios CMake dependency declares libzip **1.11.4**, obtained
unchanged at commit `6f8a0cdd24a0dc6cce9dac4a7679da784ab124ea`. Its actual zip.h
and generated zipconf.h template provide the O2rArchive public boundary. Zlib
**1.3.1**, commit `51b7f2abdade71cd9bb0e7a373ef2610ec6f9daf`, is an explicit
compiler dependency pin; LUS's libzip declaration does not pin zlib itself.
`dependencies.lock.json` hashes every fetched source file. Neither checkout is
patched by this work, including the host builds.

SoH's `platform/xbox360/assets.cpp` was inspected (SHA-256
`1a6260b658e9e1217e1454f1c42e23a55adcf1c1a2f5d5e2d791027feffdb0c3`). It uses a
custom package reader rather than this libzip boundary. No donor archive reader,
exported package, host extraction executable or host library is used as the
Xbox archive implementation.

The Xbox libzip **runtime library is not yet built**. Its desktop Win32 source
backend needs a native implementation/adaptation before link/runtime claims:

* Actual `zip_source_file_win32.h` includes unavailable windows.h/aclapi.h.
* The handle backend requires GetFileType, absent in the XDK.
* The ordinary UTF-8 filename route converts to UTF-16 and calls CreateFileW,
  absent in the XDK; Xbox native storage is exposed through CreateFileA here.
* Desktop security-descriptor preservation is optional in libzip and must be
  configured from actual SDK capabilities, not faked.
* `zip_random_win32.c` assumes desktop CryptoAPI. Its secure-random boundary and
  optional encryption support need an explicit Xbox decision/implementation.
* libzip's C feature/configuration and complete object/link closure remain to be
  verified. Passing the public consumer header does not establish any of these.

Read/seek/write/filetime, filesystem enumeration, ordinary CreateFileA and
MoveFileExA already exist as real SDK operations; the native probe records
supported and unsupported symbols individually. LocalFree, for example, **does**
compile and is not listed as a missing primitive. The existing libzip algorithms
and archive data format should remain intact when adapting that OS boundary.

## Verification and limits

Run these commands from Smash360:

```
python tools/prepare_resources_xdk.py
python tests/resources-xdk/dependencies.py
python tests/resources-xdk/run.py
python tests/resources-xdk/compile.py
python tests/resources-xdk/native_dependencies.py
```

The host dependency build compiles real zlib/libzip sources into host libraries
only, under scratch. It uses Ninja to avoid unrelated MSBuild SDK discovery
permissions and never runs zlib's source-renaming CMake step.

The host integration links actual original and generated resource/loader/archive
methods with actual libzip, JSON, binary readers and logging. Only Context service
lookup is injected by a **test-only** fixture; no ResourceManager/Archive methods
are mocked. It validates folder/ZIP reads, manifest fields, actual 64-byte legacy
headers, factories, queued worker identity, shared-future exceptions, cache hits,
batch loads, archive filtering, real ZIP replacement/reopen and retained old
resource ownership. Original FolderArchive is supplied a generic path directly
because its automatic Windows discovery is already broken; generated code tests
the corrected automatic discovery path.

Persisted original/generated resource output is byte-identical, SHA-256
`59fe401487054a0c89ff9d3332dc6d25562e7ebedfd7cfbada1c18e406fbc4e2`.
Additional generated regressions cover parallel missing loads, erasure counts,
a resource destructor reentering the cache after unlock, corrupt ZIP reads,
native sharing-induced replacement failure, and unopened archive destruction.
The original one-worker batch is reproduced as a bounded timeout after entering
the actual load. The corrected batch completes. A blocked factory proves manager
destruction waits for a real worker and permits its future to finish safely.

All 18 production resource/support translation units and the composed header
probe compile with XDK `/W3`; existing/compiler-library warnings are retained in
the per-TU logs. The eleven actual zlib compression-core units also compile with
XDK. These are object checks; there is no resource-system Xbox link, XEX, boot,
native archive execution, or application Context lifecycle claim.

Two inherited contracts remain explicitly outside the corrections above:
Archive::IndexFile hides .meta names from ArchiveManager's hash table while
ResourceLoader asks that table for sidecars, and LoadResourceProcess passes the
identifier.Path overload rather than its available Parent-aware overload. The
baseline uses the actual legacy archive format. Isolated metadata parsing tests
elsewhere do not establish full sidecar routing. These need separate evidence and
bounded fixes if the production archive path depends on them.
