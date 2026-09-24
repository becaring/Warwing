# Actual LUS libultra and audio bridge projection

`tools/prepare_libultra_xdk.py` validates pinned original hashes before emitting source-mapped overlays. It builds the nine actual libultra translation units, actual `audiobridge.cpp`, and actual `NullAudioPlayer.cpp`, together with their two required header projections. The original files remain unmodified. All must remain selected by the application source manifest.

- Small libultra modules include the actual libultra C ABI declarations directly, removing only the unrelated desktop `classes.h` umbrella dependency.
- `osContInit` probes the existing native four-slot XInput transport and calls the actual ControlDeck initialization. Desktop SDL controller-database/HID configuration and Raphnet initialization are explicit unavailable platform branches. The original status/controller-bit initialization and ControlDeck call remain.
- The complete original `osContGetReadData` algorithm still uses the LUS extended temporary and copies the game fields individually. A native assertion requires the game view to occupy six bytes.
- N64 clock duration uses the exact reduced period `1/46875000` through the existing central chrono implementation. `osSetTime`, `osGetTime`, `osGetCount` arithmetic and truncation are retained.
- AudioDmaRegistry aggregate assignment is spelled as aggregate construction plus assignment. Array capacity, clamp bounds, and actual osPiStartDma zero fill/copy behavior are retained.
- NullAudioPlayer retains its inherited upstream behavior and is compiled as a library member; this does not select it as the Xbox output backend.

## Link contract: game-owned VI and messages

BattleShip `port/stubs/n64_stubs.c` owns blocking message APIs and VI/framebuffer scheduling. The final application must link game objects first and the LUS static library lazily, as the original project does. Do not force individual LUS `os_mesg` or `os_vi` objects into the final link.

The unused LUS `os_vi.cpp` fallback still contains its original callback/event algorithm but calls the deliberately undefined `Smash360_UnavailableLusFallbackViTimer` in place of SDL's timer. Root approved this explicit fail-closed boundary: if mistakenly selected, linking must fail. There is no success stub and no second timing loop. The final linker map must establish that `os_vi` and `os_mesg` members were not selected and that these APIs resolve to game-owned definitions. This bounded object test does not establish that final link fact.

Existing upstream no-op cache/PI/timer/AI functions are retained, not newly implemented or claimed working.

## Verification

`python tests/libultra-xdk/compile.py` compiles all eleven real translation units with XDK VS2010. Native report records commands, logs and PowerPC object hashes.

`python tests/libultra-xdk/contract_run.py` compares original and generated actual AudioDmaRegistry and osPiStartDma behavior: eight-entry capacity, registered/unregistered ranges, partial copy, zero-fill and surrounding buffer sentinels. Test-side original os_pi has only its umbrella include reduced to actual C ABI headers; original function bodies are unchanged, and no services/classes are substituted. The same fixture checks central chrono conversion against the original standard ratio over positive and negative sample durations. No console/runtime/boot claim follows.
