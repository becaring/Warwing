# Current controller compiler projection

`tools/prepare_controllers_xdk.py` composes the pinned, actual current libultraship controller sources with the native input overlay. All 97 inputs are SHA-locked; the native input overlay is checked against its own original/output manifest. The application manifest must select exactly the 47 supported non-Raphnet translation units. Generated files retain upstream `#line` locations and output hashes.

The production classes, four control ports, config migration, mappings, defaults, rumble, and device manager algorithms remain real source. Changes lower ordinary-enum qualification, structured bindings, range loops, generic lambdas, container initialization, inherited/delegating constructors, contains/to_string/clamp, and the reached round operation. By-value structured bindings retain copies; reference bindings retain aliases. The constructor lowering invokes the original default-setter bodies in order. Container builders can have different allocation/copy counts than initializer lists; value/order/ownership contracts are retained.

`_XBOX` explicitly excludes unavailable Raphnet USB transport calls and members. Serialized physical-device identity and keys remain; native startup and loading a saved Raphnet rumble mapping log the unsupported capability. No default gamepad is silently chosen in place of a saved Raphnet device. Native Xbox physical operations come from `platform/xbox360/input`; this generator does not add another transport or general SDL header.

## Verification

XDK 21256 `xhash` move construction calls `_Assign_rv` without initializing
`_Mask`, `_Maxidx`, or `_Max_bucket_size`, then swaps them into the source.
The real controller refresh moves its map and immediately reuses it. In run
`20260919-220438-971`, that source map at guest `400224C0` had a zero load factor
at `+28`, recursively rehashed to 16,777,216 buckets for one controller, and
threw on allocation. The compiler projection lowers this one move construction
to default construction plus member swap, keeping node ownership and the real
refresh/routing algorithm. SDK headers and upstream sources remain untouched.
Run `20260919-221213-580` confirms the corrected controller refresh proceeds
through thousands of real game frames with Xenia keyboard-to-XInput enabled.
Menu advancement and physical-controller hardware validation remain separate.

- `python tests/controllers-xdk/compile.py`: all 47 real selected TUs compile with the XDK VS2010 PowerPC compiler; object machine type checked. Commands, diagnostics and object hashes are in `scratch/controllers-xdk/native-verification.json`.
- `python tests/controllers-xdk/defaults_run.py`: original and generated actual Ship/LUS default mapping constructors, all six tables, custom overrides and explicit empty-container fallback produce identical output.
- `python tests/controllers-xdk/lowering_run.py`: original/generated binding ownership and mutation behavior, nested/local pair bindings, contains, and 20,000 floating bit-pattern/tie/NaN/zero rounding cases pass.

These establish source/object closure and bounded host contracts. They do not establish linked application, controller hardware execution, or boot. The existing native-input test suite separately covers four-slot topology and the original six-byte game pad copy.
