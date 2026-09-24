# JSON compiler boundary

The active Xbox backend is compiled directly from Shipyard
`sources/json/json.cpp`, using `sources/json/include` and Shipyard's pinned
generator in `python/xbox360_platform/json`. This directory contains only
historical compiler probes for the unmodified nlohmann 3.12.0 dependency.

`tools/prepare_json_xdk.py` runs the shared generator and records the Smash360
compiler probe. `tests/json/backend_run.py` compares reached API behavior and
compiles the physical Shipyard backend to PowerPC.
