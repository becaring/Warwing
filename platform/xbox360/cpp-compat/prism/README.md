# Pinned Prism compiler and Fast3D shader provider

This adapts official Prism commit `1de054450e7b3c5f777d2e3dfcb228ad120c329d`
and BattleShip's pinned DX11 shader builder. It retains the current parser,
context, formula callbacks, template expansion, includes, and shader equations.
There is no second combiner implementation or old SoH shader generator.

`source-lock.json` locks all source inputs and the actual default HLSL template;
its historical helper hashes remain provenance only. Host parser packages are
installed at pinned versions by `tools/setup-host-deps.ps1` into
`scratch/host-python`. `tools/prepare_prism_xdk.py` uses Shipyard's
version-constrained `xbox360_platform.prism.PrismProjector` for compiler syntax.
Its pinned source checks, resource acquisition, builder, and debug guard remain
local. It leaves upstream unchanged and emits source-mapped files under
`scratch/prism-xdk`. Unchanged spans refer to original source lines;
adapted spans refer to their real generated locations. The pinned Tree-sitter
wheel requires CPython 3.13 x64 Windows. The former vendored bindings and donor
range-lowering script are no longer source inputs or alternate projectors.

Prepare dependencies and validate from the project root:

```
python tools/prepare_value_types.py
python tools/prepare_graphics_xdk.py
python tools/prepare_prism_xdk.py --compile
powershell -NoProfile -ExecutionPolicy Bypass -File tests/prism/run.ps1
```

Production translation units are generated `prism/lexer.cpp`, `prism/ast.cpp`,
`prism/processor.cpp`, `prism/utils/gv.cpp`, `prism/utils/invoke.c`, and
`shader_builder.cpp`, plus the physical Shipyard
`sources/graphics/shader_provider.cpp`, `sources/graphics/shader_lower.cpp`, and
the `graphics/shader_provider.cpp` decoder adapter. Compile `invoke.c` as C. Include this directory,
`scratch/prism-xdk`, Shipyard `sources` and `sources/value_types`, generated graphics headers,
and the graphics source directory. `test_shader_features.cpp`, `range_contract.cpp`,
and everything under `reference/` or `host-*` are test-only. Production links
the real interpreter's `gfx_cc_get_features` and `Fast::gfx_get_shader`.

The required production resource boundary is:

```
bool Smash360_LoadShaderResource(const std::string& path, std::string& source);
```

It must use the actual LUS resource manager's typed Shader resource loading,
with native byte order and binary resource format, and copy the Shader's string
into `source`. Includes call this same loader. No filesystem fallback, embedded
dummy template, or production substitute is provided. A missing main resource
throws a Prism runtime error that the public provider reports as `false`, with
empty source, zero float count and a diagnostic. The pinned desktop builder's
abort-on-missing-resource boundary is thus an explicit reported failure.

Syntax adaptation preserves the closure's constructor defaults, partial
aggregate initialization, scoped-enum values, and variant alternatives.
AST aggregate constructors are explicit so they do not add implicit conversions
to the variant overload set. Bounded anonymous SHADER constants 0..14 are cast
to `int`, their original `std::variant` alternative. General enum conversion
is outside the value helper's supported surface. Range lowering evaluates the
range expression, begin, then end once each, retains temporary lifetime and
reference binding, and preserves break/continue. Original range donor code
reevaluated end on each iteration; the adapted implementation corrects that.

Prism's one `SPDLOG_DEBUG` call is disabled at its normal Release active level.
An explicitly enabled debug/trace build requires real spdlog headers and their
actual compiler-compatible dependency closure; no logger shim is supplied.

Shipyard's shader provider keeps both 64-bit IDs intact through the real decoder
and uses the key's filtering and sRGB fields. The pinned DX11 builder computes
a custom shader path but loads the literal default path at lines 1547–1548.
That inherited behavior is preserved and tested, rather than silently claiming
custom top-level overrides work. Include callbacks work. The shader registry
and typed resource loading remain production integration dependencies. The
builder also retains its static float counter and therefore requires serialized
shader generation, as in the pinned implementation.

Primitive depth is not a Prism option: the pinned interpreter calculates vertex
z at `interpreter.cpp:3518` and `:3650`. The generated VS preserves the input
position. Xenos lowering packs four scalar clamp varyings into one float4 only
between vertex and pixel stages; the CPU vertex layout and VS input semantics
remain unchanged. This avoids the Xenos pixel-input-variable limit for seven
inputs plus both textures, all clamps, fog and grayscale. Unused packed
components are zeroed and never read by the generated shader. Equations,
texture coordinates, thresholds, mask dimensions and sampling remain unchanged.

Verification on 2026-09-20:

- All seven production Prism/provider XDK objects and two test objects compile.
- An unchanged official Prism host build and the generated host build produce
  byte-identical original HLSL, lowered HLSL, and float counts for 702 real
  default-template permutations. Coverage includes seven vertex inputs,
  separate alpha, two cycles, noise, fog/grayscale, alpha discard, all masks,
  replacements, clamp axes, all filter modes, and sRGB.
- All 872 unique vertex/pixel outputs compile using the real XDK `fxc.exe`.
- Include loading, missing includes, malformed source, reserved names, member
  defaults, bool/enum variant selection and resource failure behavior agree.
- Executed range tests cover temporary lifetime, evaluation order/count,
  mutable references, arrays, break and continue; the lowered fixture also
  compiles with XDK. Preparation tests reject source drift.

Outputs and full compiler logs stay under `scratch/prism-xdk`. These are host
differential and compiler checks, not PowerPC execution, an application link,
GPU interpolation validation, or a game boot. Unsupported desktop/custom HLSL
still fails explicitly. No reference tree was edited and Xenia was not run.
