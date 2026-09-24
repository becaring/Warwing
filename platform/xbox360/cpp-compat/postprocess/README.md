# Current postprocess compiler projection

`tools/prepare_postprocess_xdk.py` hash-locks and source-maps all seven current
Fast3D postprocess translation units and `fast/debug/GfxDebugger.cpp` into
`scratch/postprocess-xdk/generated/src`. It consumes the canonical Fast3D
headers and the existing filesystem, synchronization, formatting and math
boundaries. No replacement manager, renderer, parser or resource facade is
introduced.

Keep `LUS_POSTPROCESS_TRANSPILER` **undefined**. This is upstream's default OFF
configuration, and its `#ifdef` branches would be enabled by defining it to zero.
Both actual transpiler implementations retain their original failure messages
and return values. Xenos independently reports its actual lack of postprocess
support. Parsing, discovery, presets, normalization, chain management and
diagnostics remain present and compile.

Projections lower scoped enums, aggregate/member defaults, range loops with one
cached end iterator, if initializers and initializer-list vector construction.
The filesystem iterator free begin/end functions retain the actual shared
filesystem iterator behavior. Runtime diagnostics use the existing native mutex.
The debugger's one-element vector assignment retains the actual breakpoint path.

`ParseParameterFloat` uses the SDK's real `_Stofx` conversion with its end pointer
on Xbox, and `std::strtof` on the host. The SDK internally converts through
double, so pathological decimal halfway cases can differ from a correctly
rounded direct float conversion. The host differential does not validate that
native CRT difference. `RoundPixels` retains round-half-away-from-zero for
ordinary representable pixel dimensions through the existing viewport helper;
NaN, infinities and out-of-range conversions are outside the tested domain.

Validation:

```
python tools/prepare_postprocess_xdk.py --compile
python tests/postprocess-xdk/run_host.py
```

All eight complete translation units compile with the real XDK. The host test
compiles original and projected implementations and compares complete output for
14 preset cases, six Slang sources, three GLSL fixtures, both bundled GLSL files,
transpiler-OFF failures, inactive chain passthrough, diagnostic transitions and
debugger breakpoint transitions. Its diagnostic translation unit is an exact
extraction of the real source loader's mutex-protected state and functions; it
does not substitute behavior. The projected host test links the real native
synchronization implementation. Full source-loader filesystem/resource loading,
an active postprocess rendering chain, target execution and application linking
are not claimed by these checks.
