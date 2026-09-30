# Resources and archives

`tools/prepare_resources_xdk.py` adapts the pinned LUS ResourceManager,
ResourceLoader, and archive implementations. Inputs are checked against
`sources.lock.json`; generated files go under `scratch/resources-xdk`.
Use `tests/resources-xdk/compile.py` for the required include order.

Keep resource changes synchronized with their headers and the real BS task
queue. The projector separates syntax changes from these runtime corrections:

- Cache writes and unloads use the resource mutex. Removed resources are kept
  alive until after unlock so destruction can safely reenter the resource code.
- Shutdown drains the worker pool before destroying its mutex and cache.
- A batch already running on a single-worker pool loads its children directly,
  avoiding a wait on work queued behind itself.
- Missing archive lookups do not insert entries. Concurrent mounting still
  requires the caller to serialize writes to the archive map.
- Folder paths use consistent separators. ZIP reads check size, short reads,
  CRC validation, and close errors; handles are released on failure.

The ZIP backend uses the pinned libzip and zlib dependencies. See the
[native libzip guide](../libzip/README.md) for its platform configuration and
tests. Older audit statements that libzip was not built describe an earlier
integration stage.

Run from the root after dependency setup:

```powershell
python tools/prepare_resources_xdk.py
python tests/resources-xdk/dependencies.py
python tests/resources-xdk/run.py
python tests/resources-xdk/compile.py
python tests/resources-xdk/native_dependencies.py
```

Host comparisons use real loaders and archives with test-only Context lookup.
They do not establish scene rendering, Xbox storage behavior, or hardware
performance. Verify affected archive loads and scene changes on the runtime
image after rebuilding.

The [archived audit](../../../../archive/subsystems/cpp-compat/resources/README.md)
preserves the detailed API, dependency, and test history.
