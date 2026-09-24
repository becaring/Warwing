# Native libzip boundary

`tools/prepare_libzip_xdk.py` generates the real libzip 1.11.4 C runtime from
`upstream/dependencies/libzip`, revision
`6f8a0cdd24a0dc6cce9dac4a7679da784ab124ea`. Compression uses real zlib 1.3.1,
revision `51b7f2abdade71cd9bb0e7a373ef2610ec6f9daf`. Both source checkouts remain
unmodified. The root dependency lock contains the full revisions. This module's
source lock verifies the runtime C/header inputs and generator templates.

The libzip entry, central-directory, compression, CRC, encryption, source-state,
error, and archive ownership algorithms are retained. Generated sources carry
original `#line` mapping. C compilation needs only one core syntax lowering:
two declarations in `_zip_dirent_apply_attributes` move to their block start,
with the initialized declaration's assignment left in its original position.
The error-string source comes from libzip's own CMake generator.

## Platform configuration and contract

The runtime is static, big-endian on `_XBOX`, with 32-bit `size_t` and the actual
fixed-width SDK integer types. Host verification uses its actual 64-bit size.
Store and deflate and traditional PKWARE encryption are built. Optional AES,
BZIP2, LZMA and ZSTD backends are disabled by configuration; the real library
returns its unsupported compression/encryption errors for those operations.

The real Windows named-source and ANSI operation table use native
CreateFileA/ReadFile/WriteFile/SetFilePointerEx/GetFileAttributesExA/MoveFileExA.
The normal `zip_source_file[_create]` path resolves through
`xbox_compat::filesystem::absolute`, normalizes separators and captures the
absolute name before creating the source. App startup must first call
`InitWorkingDirectory` with a validated mounted directory. No default device
or save-container policy is added here. Native filesystem errors retain their
libzip Windows-to-errno mapping; they are not silently converted to absence.

XDK has narrow filename APIs. Normal archive filenames are therefore restricted
to ASCII and non-ASCII names return `ZIP_ER_INVAL`; this is an explicit supported
subset, not a claimed UTF-8 filesystem conversion. Names *inside* ZIP archives
keep libzip's UTF-8 handling. Direct `zip_source_win32a` remains the native narrow
API. The wide-source API and arbitrary HANDLE source API preserve their public
validation and return `ZIP_ER_OPNOTSUPP`. Failed source creation does not acquire
or close the caller's handle. There is no invented GetFileType implementation.

Desktop security descriptor copying and reparse-point handling are excluded
from the Xbox configuration because those desktop contracts are unavailable.
Xbox named-source status uses actual directory attributes and high/low file
sizes. The inherited CRT FILE/descriptor source retains libzip's configured
`long` seek range; the production named archive path uses native 64-bit seeking.
This is not a complete replacement for every optional libzip platform backend.

`zip_secure_random` calls real XNetRandom. The application owns XNet startup and
cleanup; this library adds no process-lifetime network initialization. A service
failure returns false. Libzip's existing random fallback remains unchanged.
Unencrypted asset reads do not need entropy. Windows verification uses actual
CryptoAPI and releases its provider even when generation fails.

SoH360's `platform/xbox360/platform.cpp` supplied the native entropy API evidence
(source hash recorded in `sources.lock.json`), and its asset code confirms the
XDK CRT 64-bit seek API. Searches found no donor libzip adapter. The donor's
custom package format, archive classes, or host extraction binaries are not
runtime dependencies.

## Separate lifetime correction

In upstream `_zip_win32_named_op_commit_write`, successful CloseHandle consumes
`ctx->fout`, but a later attribute/rename failure leaves that stale value for
rollback to close again. The generated correction clears `ctx->fout` immediately
after successful close. The test deliberately allocates another native handle
after a forced replacement failure and verifies rollback leaves it usable.
This behavior correction is separate from syntax/platform lowering.

## Reproduction and integration

Run `python tests/libzip-xdk/compile.py`, then
`python tests/libzip-xdk/run.py`, and
`python tests/libzip-xdk/generator_contract.py` from the project root. The host
reference library comes from `tests/resources-xdk/dependencies.py`.

Generated header/source root: `scratch/libzip-xdk/generated`.
Native libraries: `scratch/libzip-xdk/xdk/zip.lib` and `zlib.lib`.
The zip library contains `native_boundary.cpp`; link the shared filesystem and
async implementations once, plus normal XDK platform libraries. Do not link
the desktop host libraries into the Xbox application. Exact compile commands,
unit lists, source/output hashes, and diagnostics are saved under scratch.

Verification covers original-versus-adapted stored/deflated binary data, UTF-8
entry names, a ZIP64 local header, empty files, entry seek/tell, bounded file
sources, writes/replacement/rename/delete, traditional encryption, corrupt CRC,
truncation, unsupported compression, missing files, sharing-induced replacement
failure, handle lifetime, unsupported API errors and initialized logical cwd.
It also links the *actual* current ResourceManager/Loader/O2r classes against
this generated library and reproduces their reference result. Test-only Context
service lookup is described by the resource tests; no archive/loader methods
are mocked. The extracted 700000-byte differential payload hashes to
`0d7df2af06150874c13dd4d25ed9e0526e9549203ecd836345e2939f1f140996`.

All runtime C units, the native boundary, and eleven zlib core units compile with
XDK `/W3` into static libraries. Existing upstream width-conversion warnings are
retained in logs. There is no Xbox execution, final application link, XEX,
emulator, hardware filesystem, or boot claim in these checks.
