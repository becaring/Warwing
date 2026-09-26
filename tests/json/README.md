# JSON verification

Run from the repository root:

```
python tools/prepare_json_xdk.py
python tests/json/test_generation.py
python tests/json/backend_run.py
```

The backend runner builds the same rich and edge programs against original
unmodified JSON3.12.0 and against the explicit Xbox compiler-library backend,
requires byte-identical output, compiles backend+API instantiations with actual
XDK cl, checks PowerPC object identity, and requires unknown conversions to fail.
Commands, stdout/stderr and verification hashes are under `scratch/json-xdk`.
`reference.cpp` covers the reached rich contract. `edge_contract.cpp` includes
4000 floating bit patterns and diagnostics. Test inputs never touch user config.

`run.py` separately preserves the original generic-template feasibility probes
and the early actual RFC6901 leaf lowering. Its expected original JSON/XDK failure
does not describe the concrete backend's compilation result.

`tests/json-consumers` validates original LUS consumer source against both
libraries. This test suite does not replace those consumers.

See `platform/xbox360/cpp-compat/json/README.md` for source mapping, build include
order and explicit unsupported API vocabulary. No test here creates a standalone
XEX or claims game/console execution.
