# BattleShip Xenos backend integration

This directory adapts the pinned BattleShip Fast3D interfaces, without replacing
its interpreter, combiner equations, scene logic, display-list normalization, or
resource/relocation ownership. It now forms the linked native application;
current XEX, production validation and limitations are recorded in
`../../../BRINGUP.md`.

`source-lock.json` pins the upstream interface inputs. The renderer, shader
cache, and presentation pacing use the Shipyard checkout directly;
preparation does not rewrite those implementations.

Run from the project root:

```
python tools/prepare_graphics_xdk.py --compile
powershell -NoProfile -ExecutionPolicy Bypass -File tests/graphics/run.ps1
```

Generated output is under `scratch/graphics-xdk`. Unchanged source spans retain
their original `#line` locations; adapted spans refer to their actual generated
file/line. Headers keep every upstream virtual operation and data member.
Scoped postprocess enums use four-byte wrappers with their original enumerator
values; in-class initializers become constructors. This generated header family
must be shared with the eventual interpreter build, not mixed with separate
handwritten interface facades. ImTextureID remains `void*`, as explicitly set in
the pinned LUS ImGui patch.

The concrete `Fast::GfxRenderingAPIXenos` adapts the shared Shipyard renderer.
`Fast::GfxWindowBackendXenos` supplies the current window
interface and uses the display's reported refresh rate for presentation pacing.
There is no donor callback table or alternate game frame loop. The application
must register these classes in the real Fast3dWindow backend selection.

Implemented backend adaptations:

- full two-uint64 shader identity, filtering and sRGB key fields;
- six owned texture bindings, with mask/replacement sampler behavior following
  their base tile and separate mask dimension uniforms;
- current CCFeatures and vertex layout, fed by the required Prism provider;
- independent depth comparison/write flags, color-write suppression;
- attachment-selective clears, normalized color-region clears;
- rectangular framebuffer copy, sample retention, native RGBA5551 readback;
- framebuffer destruction and slot reuse;
- native texture lookup for GUI rendering and framebuffer sampling;
- source/entry/profile shader cache with ABI version 2 and a Smash-specific path
  and save-worker callback.

`Shipyard_BuildFast3DShader` is compiled from Shipyard's
`sources/graphics/shader_provider.cpp`; this adapter supplies BattleShip's
feature decoder. The pinned Prism boundary is described in
`../cpp-compat/prism/README.md`. Its real typed LUS resource-loader callback and
the interpreter remain required link dependencies. The pinned DX11 builder's
top-level custom-path bug is retained and documented there. The old SoH shader
generator is not imported into the production output. The subsequent
`Smash360_LowerShader` only lowers supported HLSL syntax to Xenos SM3. Unknown
resource syntax fails explicitly instead of substituting a different shader.
The four clamp varyings share a float4 between shader stages to fit the largest
Fast3D layout within Xenos's pixel-input limit; VS input semantics and the CPU
vertex layout remain intact.

`services.h` lists required real platform services and window/pointer event
operations. Their implementations are not hidden behind success-returning
defaults. The Smash adapter forwards the shader-worker write to Shipyard:

```
bool Smash360_WriteShaderCacheRecord(const std::string& record, bool truncate);
```

Optional postprocessing remains unsupported: the inherited capability gate
returns false. This includes CRT pass chains, mipmapped/float postprocess
attachments, static postprocess textures, and slang programs. These operations
are outstanding parity work, not silently considered implemented. Custom
Fast3D shaders also require actual provider integration and supported-source
validation; arbitrary desktop HLSL is not promised to fit Xenos SM3.

Verification on 2026-09-20:

- XDK objects compile for native renderer, shader cache, HLSL lowering, window
  backend and a test allocating both concrete backend classes.
- Host tests verify key separation above bit 32, filtering/sRGB distinction,
  generated member defaults, six shader resource slots, mask dimensions,
  equation/alpha-threshold preservation and explicit rejection behavior.
- The actual lowered six-slot fixture compiles with XDK `fxc.exe` as `ps_3_0`.
- Source-preparation tests reject input drift and verify all virtual operations
  survive generated-header adaptation.

Compiler warnings remain in imported native code for alignment padding,
bounded integer narrowing, signed comparisons, and the XDK's device factory
macro. Full logs are retained. Host fixture compilation uses warnings-as-errors.

These checks do not prove framebuffer orientation, region/copy/MSAA behavior,
depth-only writes, memory lifetime under GPU load, complete shader permutations,
or game output. Those initial object checks did not include application/XEX
execution. Subsequent real-game Xenia validation is recorded in
`../../../BRINGUP.md`, including the published-framebuffer lifetime fix and native
1x/2x/4x MSAA. Physical Xbox 360 validation remains required.
