# Xbox filesystem contract

`filesystem.h` forwards to Shipyard's `sources/filesystem/filesystem.h`.
The application compiles Shipyard's `sources/filesystem/filesystem.cpp` directly
and links its `sources/async/native.cpp` for the working-directory mutex.
The API uses the XDK's `std::error_code` and `std::system_error`.

## Startup and path resolution

Application startup must call `InitWorkingDirectory(fullyQualifiedDevicePath)`
before any relative filesystem call. The supplied path must name an existing
directory. Xbox has no process cwd API: `current_path()` returns this synchronized
logical cwd, and `current_path(path)` validates a real directory before changing it.
Before initialization, relative native operations fail with `ERROR_NOT_READY`.
No default drive or mount is chosen here. Windows builds use the real process cwd;
the test-only `SHIPYARD_TEST_LOGICAL_CWD` build executes the Xbox cwd code on Windows.

Device names such as `game:`, `cache:`, and a caller-mounted XContent name remain
part of the path. Both separators are accepted. A leading separator keeps the cwd's
device; a fully qualified right-hand operand replaces the left-hand path when
joining. `lexically_normal()` removes `.` and resolves `..`, stopping at the root.
Device-relative paths such as `game:foo` are unsupported on Xbox. Names are native
narrow bytes, with no claimed UTF-8/UTF-16 conversion. UNC and malformed wildcard,
embedded-NUL, or extra-colon names fail explicitly at the native boundary.

The logical cwd does not alter CRT streams. Generated call sites that open a
relative path through `ifstream`, `ofstream`, or `fopen` must first obtain
`absolute(path).string().c_str()`. Config's stored pathname should be supplied as a
fully qualified application path. Selecting that application path and mounting
XContent remain startup/storage policy outside this adapter.

## Supported API

* `path`: narrow string constructors; `string`, `generic_string`, `c_str`, string
  conversion; empty/clear; root_name/root_directory/root_path/relative_path;
  is_absolute; parent_path/filename/extension/stem; lexically_normal; make_preferred;
  replace_extension; `/`, `/=` and lexical comparisons.
* Throwing and `error_code&` overloads: current_path getter/setter, absolute,
  status, exists, is_directory, is_regular_file, file_size, last_write_time,
  create_directory, create_directories, copy_file, remove (file or empty directory),
  rename. `filesystem_error` retains path1,
  path2 when relevant, and the native system error code.
* `directory_iterator` and `recursive_directory_iterator`: default/end,
  path constructors with throwing/error overloads, dereference/arrow, prefix
  increment, increment(error_code), equality, free begin/end. Copies share a
  single-pass native search. Entries expose path and is_directory/is_regular_file
  with both error modes. Search handles close on exhaustion, failure or final
  owner destruction. Recursion uses the real directory entries and reports
  access/enumeration failures; it never manufactures entries or skips errors.
* Explicit native helpers `read_file` and `write_file`: whole-file bytes with
  error-code results, native sharing rules, partial-transfer loops and closed
  handles. Reads cap at 128 MiB (`ERROR_BUFFER_OVERFLOW`); writes flush file bytes.
  These helpers do not replace archive streaming and do not promise atomic save
  replacement or flush/mount an XContent container.

Missing files are distinct from native failures: status(error) reports not_found
and the native error; throwing status returns not_found without throwing;
exists(error) clears a known not_found error, while is_directory(error) preserves
it. Access denied, sharing violation, malformed names, and iterator failures stay
visible. `rename` uses replacement/write-through and does not copy across devices.

This is a bounded subset. General copy/remove_all, temporary-directory discovery,
symlink creation, canonicalization, permissions, wide paths, iterator depth/postfix,
and the complete standard path constructor/iterator API are absent and fail
compilation if requested. Xbox lacks reparse attributes; host status follows
reparse targets, while default recursive traversal does not descend through
directory links. Arbitrary Windows reparse behavior
and concurrent external filesystem mutation are not made portable by this layer.

## Audited consumers and provenance

`sources.lock.json` pins 23 actual current LUS/BattleShip files. Running
`tools/prepare_filesystem_xdk.py` rejects changed sources, writes an operation/line
audit to `scratch/filesystem-xdk/provenance.json`, and lowers the real `Directory.h`
filesystem include/namespace and one range-for with `#line` mappings. Its existing
CreateDirectory catch-all is preserved; the adapter itself does not suppress that
error. The generated header is a compile fixture and available integration input,
not an installed replacement for upstream headers.

| Caller | Required boundary |
| --- | --- |
| Config.cpp | exists/is_regular_file before existing stream reads/writes |
| ConsoleVariable + DiskFile/Path | exists/remove, filename/stem/parent, joining and explicit stream path conversion |
| ArchiveManager.cpp | directory_iterator, entry extension, absolute(entry), file/directory status |
| FolderArchive / Directory / hires | recursive enumeration, entry is_directory, generic_string, create_directories |
| port.cpp mod mounting / postprocess | error-code iterator and status, filename/extension/stem |
| Context / app_paths | path joins, create_directories, error-code exists; application-root policy still separate |
| first_run / ShaderDownloader | audit includes copy/remove_all/temp operations; these desktop facilities are not supplied |

The historical donor `platform.cpp` SHA-256 is recorded in `sources.lock.json`:
`18ed5127d03e933df041a33f1691becf29a058580f335535f3efcd2c832cd419`.
The full donor copy is no longer an input or implementation here. Both active
consumers compile the physical Shipyard `sources/filesystem/filesystem.cpp`.

## Verification

Run `pwsh -File tests/filesystem/run.ps1`. It builds with host MSVC `/W4 /WX`,
compares shared path and real filesystem behavior against `std::filesystem`, and
tests byte I/O, readonly/sharing errors, missing vs failure, enumeration, validated
cwd changes, rename replacement and deletion. A second build runs the Xbox logical
cwd branch, including failure before initialization and unchanged host process cwd.
Fixtures are unique children of `scratch/filesystem-xdk` and individually removed.

The same run compiles filesystem.cpp, async/native.cpp and the actual generated
Directory header plus current Config/Archive/Path call-shape probe with XDK
`/W4 /WX`, and verifies unsupported remove_all is rejected. These are objects only;
full Config/Archive translation-unit integration and Xbox storage execution remain
separate validation. No standalone XEX or boot claim is made.
