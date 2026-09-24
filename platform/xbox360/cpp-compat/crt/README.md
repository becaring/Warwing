# Native formatting

`sources/crt/format.cpp` in the pinned Shipyard checkout is the only formatting
implementation. Smash360 compiles it directly. The local `snprintf.h` maps the
existing `Smash360_Vsnprintf` callers to `Shipyard_Vsnprintf` and includes the
canonical declaration. Selected game C translation units force-include the
physical Shipyard header; no generated copy is needed.

The XDK formatter lacks C99 `z`; Shipyard strips it only from parsed integer
conversions after verifying Xbox ILP32 widths. Ordinary format calls use no
heap allocation. Native Xbox execution is not established by the host and PPC
compile tests.

Run `python tests/crt/run_tests.py` and `python tools/prepare_crt_xdk.py` from
the Smash360 root for the ILP32 formatting contract and PPC object receipt.
