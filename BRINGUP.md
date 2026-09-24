# Smash360 bring-up status

2026-09-21 current SoH-parity hardware-test package:
`D:\Projects\Smash360\dist\Smash360\Smash360.xex`, SHA-256
`3E553C2F6AB9CED20C1183CE6A33B5EBE13FC7FD55194FB85FD6441E28534914`.
XDK build and linked-code checks pass. Console performance and visual validation
of this package remain pending. See the final entry and `SOH_PARITY.md` for the
systematic donor audit, transferred optimizations and contract differences.

2026-09-20: **native boot and genuine gameplay confirmed on physical Xbox 360.**
The user's hardware log records successful storage recovery and mount; the
103-second recording `C:\Users\crisj\Videos\2026-09-20 01-57-33.mp4` shows Link
on Hyrule Castle, a stage transition, and the Yoshi-team fight. Original models,
textures, HUD and the controller-driven game path are visible at 720p / 1x MSAA.
This establishes the hardware bring-up milestone, not finished performance/audio
or exhaustive game correctness. Evidence: `scratch/evidence/hardware-boot-F0F4F3DC`.

2026-09-19: **genuine visible native Xbox boot achieved in Xenia.** The real
BattleShip/Smash application initializes its services, runs the actual coroutine
scheduler, loads the original opening sequence, renders Smash characters and
environments through Fast3D/Xenos, and naturally reaches the title scene.
User evidence shows Link on the opening cliff; a subsequent direct window
capture shows the opening character silhouettes. This is real production output,
not a synthetic scene. The user subsequently requested continued fixes for
audio distortion, missing sprites/text, and corrupted textures.

First visible build SHA-256:
`FC19711BA12DA222AE34A6A975937F4AB9CFD06C8C7C007196FFE68459F7071E`.
XEX: `D:\Projects\Smash360\scratch\application-xdk\native\build\Smash360.xex`.
Frozen XEX/EXE/map, build log, runtime log, launch record and user screenshot:
`scratch/evidence/first-visible-boot`. Run: `20260919-221213-580`.

Earlier RDP diagnostic XEX SHA-256:
`8B6F64BB35CC53948BF83822008AE79185D187171516F4BDC2077EBDEB9537F2`.
This retains granular stage/work logging and corrects XDK RDP value-initialization.
XDK/link/PPC checks, actual-header differential tests and real Xenia intro runs
pass. The room stayed intact in four captured starts with three character pairs;
the intermittent graphics report still needs user confirmation, including Link.
The latest console log confirms execution of the corrected startup defaults
and provides granular profiling; visual confirmation of the intro remains pending.

First physical-console-validated XEX SHA-256:
`F0F4F3DCFC69EB158FFC50ABB2047215D994B5CECC3BF2EA78C713744410F3CD`.
That physical-console build is frozen in `scratch/evidence/hardware-boot-F0F4F3DC`.
The current hardware-test copy is `D:\Projects\Smash360\dist\Smash360\Smash360.xex`.
The physical-console build retains the early-display
contract correction and adds one guarded retry when storage selection is
interrupted during sign-in notifications. Hardware attempt one cancelled with
two pending sign-in events; after the UI closed, the same-profile retry succeeded
and mounted `smashsave:\`. Real gameplay followed. XDK/link/host checks pass;
Xenia run `20260920-015428-149` also reaches the real runtime normally. MSAA still
defaults to 1x. The exact internal XAM cancellation trigger remains unresolved;
the bounded recovery is documented rather than treated as an unconditional retry.

Earlier efficiency XEX SHA-256:
`EF235E058847180B3159C0DF14F0617763591713DD0A39045E164C28F0387B4E`.
That package launched its real opening sequence in Xenia in run
`20260920-000240-719`, with native 1x MSAA and both runtime archives loaded from
the package. This includes the framebuffer-clear and input-poll efficiency
changes below, with no diagnostic overrides. Native build, production symbol
ownership audit and PPC logger regression passed. Evidence is preserved in
`scratch/evidence/clear-reuse`. Its first hardware test exposed the storage
selector failure documented below.

Earlier framebuffer lifetime-fix XEX SHA-256:
`C1E1E111A5ECEACA13542A78A70C48F67D8961DD04CD62FA06A9DD6AB2829B50`.
This build introduced the controller
cursor, exact shader-binding constant reuse, and the held-frame texture lifetime
fix. The user confirmed that cursor/settings interaction, internal-resolution
changes, and MSAA work. Run `20260919-233953-521` exercised native 1x/2x/4x MSAA,
resolution changes across 720p, and one through five EDRAM tile passes without
reproducing the freeze. Build, launch, runtime and diagnosis evidence is preserved
in `scratch/evidence/framebuffer-lifetime`. This earlier build was not hardware-tested.

Earlier verified gameplay XEX SHA-256:
`E7E35E777413F4E78009EC6DF047BE57C63B504C3F62E2875D954A232D805926`.
A runnable snapshot with archives,
EXE/map and evidence is in `scratch/evidence/verified-gameplay`.
Visual/gameplay recording: `C:\Users\crisj\Videos\2026-09-19 22-57-03.mp4`,
recorded against timing build `083F00F6684FB5EE7D51798D84E3ABDAF5731A11F46F6AED0FF3731312191E9A`
in run `20260919-225653-135`. That subsequent gameplay build changes only shader
cache storage/diagnostics. Cache persistence run: `20260919-230302-707`;
warm-cache validation run: `20260919-230418-569`.
The additional recording `C:\Users\crisj\Videos\2026-09-19 23-03-37.mp4`
covers that XEX's first cache-populating run: character selection,
Yoshi-versus-Link stage card, spawn effects, HUD and playable Hyrule Castle.
Its images retain the visual correction; the accompanying run still has
presentation stalls and audio underruns. This recording predates the warm-cache
restart at 23:04:18 and is not evidence that audio was fully fixed. Contact
sheet: `scratch/evidence/verified-gameplay/cache-first-run-recording.jpg`.

**Follow-up visual fix verified:** the XDK Gfx packet layout correction restores
original menu text, portraits, HUD sprites and textures. The user's
`2026-09-19 22-57-03.mp4` records the real 1P menu, Link-versus-Link stage,
stage-clear results and Yoshi stage; the user reports that everything looks
correct. This is evidence for those exercised paths, not exhaustive renderer
or gameplay verification. Physical Xbox controller input is verified in
Xenia: run `20260919-222638-641` progressed through Title (1), ModeSelect (7),
VSMode (9), and PlayersVS (16), corroborated by the user's second video.
Physical Xbox gameplay is now observed as described above; exhaustive gameplay
correctness remains unverified.
Full regeneration and XDK rebuild passed (diagnostic XEX SHA-256
`DDA493FD7DF51FE5E90B747993A86EB3BD3FE7D9626AB1983F55EE362394016E`);
a completely empty scratch directory has not yet been tested.
**Remaining audio issue:** the captured pre-XAudio PCM sounds clean to the user,
but real-time playback underruns during slower frames. Five-second queue/timing
reports distinguish these from XAudio engine glitches (zero in observed runs).
Opening samples show 1–2 ms game update time, roughly 4–11 ms rendering, and
12–22 ms inside Present. Some gameplay windows sustain about 60 ticks/second
without underruns; others do not. No silence, extra game ticks, sample dropping,
rate changes or asynchronous scheduler shortcut was introduced.
After correcting cache storage, the next real launch loaded 199 cached shaders.
Warm opening windows reached 299–300 frames in about five seconds, with zero
or one underrun in those windows, substantially better than the uncached run.
This is an observed improvement, not proof that all audible dropouts are gone.
Authoritative upstream checkouts remain unmodified; Xbox
implementations and generated compatibility sources are isolated in this tree.
The supplied ROM has been verified and the real asset archive extracted.

Compiler evidence (object checks alone do not prove runtime behavior):

- All 486 selected game C translation units compile as C with XDK. The current
  first-visible-build `scratch/game-xdk/BattleShipGameC.lib` SHA-256 was
  `70c5534c82ebdbca15fdcfc98461b646d90322dfaa02a50267c78df69cfbee74`.
  There are 353 resolved typed generic operations and no remaining implicit
  function declarations. `platform/xbox360/game-compat/ABI-DIAGNOSTICS.md`
  distinguishes an inherited reachable results-screen uninitialized index from
  a dead decompilation artifact. Neither was silently patched for compilation.
- The full pinned Fast3D interpreter and paired Texture implementation compile
  with XDK. Actual math/combiner outputs match the pinned originals in host
  comparisons. The low-address desktop DLL exception is provably unavailable
  on Xbox under the SDK's XEX address layout; trusted asset ranges remain intact.
- Current Config, CVar, Audio registration, resource manager/archive classes,
  spdlog queues/sinks and ImGui core compile through isolated compatibility
  sources. Original/generated consumer comparisons cover their documented
  contracts. The combined application now links and executes initial startup.
- The actual Gui, Fast3dWindow, Window and mouse-state sources compile, along
  with the native GUI initialization and shader-resource callbacks. All eight
  original frame/viewport presentation method bodies remain unchanged. The
  155,711 original FontAwesome bytes are verified in the native Gui object;
  an explicit numeric initializer avoids XDK's 65,535-byte string limit.
- All 47 selected controller translation units and 12 actual GUI widget/resource
  units compile. Context and its 14 unique lifecycle/bridge sources compile.
  Native libzip/zlib archives are now built; their original/generated host
  resource integration tests pass. Remaining application integration and the
  final link have now completed; runtime validation remains in progress.

The compiler projection currently uses official fmt 4.1.0 instead of the modern
bundled formatter. Integer/string/pointer formatting and up to 39 diagnostic
arguments are checked; default floating diagnostic spelling differs. This is
an explicit temporary dependency deviation, not full fmt API equivalence.
The source audit now inventories 328 formatter/logging calls, including 68
direct fmt calls. Reviewed non-diagnostic IDs/labels use string, integer or
pointer forms, covered by the formatter comparisons. Details and the remaining
runtime validation limits live beside the format/logging adapters.

Xbox has no implemented Raphnet USB HID transport. Its desktop transport and
mock source are excluded explicitly; saved Raphnet identities remain distinct
and report unavailable rather than becoming a synthetic controller. The actual
Xbox XInput implementation retains four physical slots and normal mappings.

## Enhancement menu controls

Use the physical Xbox controller:

- Back/View opens or closes the menu and opens it in cursor mode.
- Right stick moves the cursor; A clicks or drags; B right-clicks.
- LT/RT scroll up/down. R3 switches between cursor and existing D-pad navigation.

The user confirmed that the cursor and settings respond. This reuses SoH360's
controller-pointer behavior behind BattleShip's actual menu-visibility and LUS
input-capture policy. Game input ownership and all four controller slots remain
intact. Native keyboard/text entry is still unavailable. R3/disconnect edge cases
have source review but have not received explicit user interaction validation.

## Verified input

Super Smash Bros. Nintendo 64, USA original retail v1.0, NTSC-U, game code NALE.
Prefer raw big-endian Z64 format, saved as:

`D:\Projects\Smash360\baserom.us.z64`

Canonical SHA-1: `e2929e10fccc0aa84e5776227e798abc07cedabf`

Canonical MD5: `f7c52568a31aadf26e14dc2b6416b2ed`

These are pinned BattleShip's own `BUILDING.md` / `config.yml` identifiers.
N64/V64 byte orders can be normalized and then checked; the canonical hash is
for Z64 bytes. No modified ROM, Remix patch or substitute asset archive is used.

The user supplied `Super Smash Bros. (USA).n64` (16 MiB). Its header identifies
halfword-swapped V64 order despite the extension. `tools/normalize_rom.py`
preserves the original and validates the normalized bytes against the canonical
hash before writing `baserom.us.z64`. Evidence: `scratch/audit/rom.json`.
The original dump SHA-1 is `0fd35ae9976b4fe68ece1c6f2d9156d913ccf076`.

Pinned Torch built on the host and extracted `scratch/assets/BattleShip.o2r`
(12,114,884 bytes). ZIP CRC checks and all 2,132 expected reloc resource paths
pass. Original shader resources form `scratch/assets/f3d.o2r` (19,412 bytes).
These checks prove extraction/inventory, not runtime resource correctness.

## Sources

| Source | Exact revision |
| --- | --- |
| JRickey/BattleShip | `07d04c5a8d3b1b712e2a749cbdd3812588bdb756` |
| JRickey/ssb-decomp-re (BattleShip gitlink) | `2898d4d94e998ddb4e971addf7f6d85a39792f3d` |
| JRickey/libultraship (BattleShip gitlink) | `89d9de83a8d09bd7d3b7bc7f8d08554ee2ce8459` |
| JRickey/Torch (BattleShip gitlink) | `3aa9c9739af95659f19adc73afeb12df93957fc3` |

All four checkouts are present under `upstream/BattleShip` and verified clean.
The top-level checkout is detached at the lock. No Bromurokk/Xenos64 Smash port
was used. All supplied reference trees were kept read-only.

SoH360 is the current platform donor, not upstream SoH HEAD. Its original
Shipwright baseline is 4.0.5 / `6e2c38895bb40492bd0361fec76aa83278d3f68a`.
Local Xbox files are identified by SHA-256 in
`scratch/audit/soh360-donor-hashes.json`; that baseline commit alone does not
identify the donor's local platform implementation. Imported files carry
separate provenance beside their platform/compatibility implementations.

## Reproduce work completed so far

From `D:\Projects\Smash360`:

```powershell
& .\tools\fetch-sources.ps1
python -B .\tools\audit_sources.py
& .\tools\probe-xdk.ps1
& .\tools\setup-host-deps.ps1
& .\tools\build-assets.ps1 -Rom '.\Super Smash Bros. (USA).n64'
```

`fetch-sources.ps1` fetches the locked source and exact submodules, refusing to
replace dirty work. Network access and Git's bundled Unix tools are required.
This environment's restricted sandbox could not run Git's submodule helper;
the same script passed with the normal desktop Git runtime. No global Git
configuration was changed.

The source audit records clean revisions, donor hashes and 4031 lexical audit
candidates across 300 files. Matches include comments/inactive branches and
are a portability review worklist, not a semantic completeness claim.

The XDK probe uses the installed `XEDK`, falling back to
`C:/Program Files (x86)/Microsoft Xbox 360 SDK`. It generates an audit-only
copy of the real BattleShip Win32 coroutine source with two transformations:
windows.h -> xtl.h, and scalar pointer thread_local -> __declspec(thread).
This follows SoH360's existing TLS syntax. Original line mapping and file/compiler
hashes are retained in `scratch/audit/coroutine-provenance.json`.
Compilation produces `scratch/audit/coroutine-xdk-tls.obj`. This is not an XEX,
application build, linked scheduler or execution test.

Host assets require Python, CMake, Git and VS2022 C++ tools. The asset build
script uses the pinned Torch recipe with SSB64/NAUDIO enabled and unrelated game
extractors disabled, then runs the original BattleShip generators with outputs
redirected into `scratch/generated`. The upstream symbol generator includes
1,770 unresolved `STUBBED` symbol definitions already present in BattleShip;
these are inherited, not new Xbox implementations. Reachability must be traced
if one is encountered during real boot. No substitute resource is generated.

Compiler/compatibility verification commands (not application builds):

```powershell
& .\tools\test_async_compat.ps1
& .\tools\test_environment.ps1
python -B .\tools\prepare_binary_reader_xdk.py --help
python -B .\tools\prepare_game_xdk.py --help
```

See `platform/xbox360/game-compat/README.md` for actual C source selection and
compile instructions, and the compatibility READMEs for supported contracts.
The C manifest is generated from pinned CMake and independently checked with
CMake's evaluator. Failed objects are retained as blockers, not excluded.

The combined VS2010/XDK 2010-01 projects now exist. With the documented module
projections and audited game objects already generated, run:

```powershell
& .\platform\xbox360\build.ps1
```

To regenerate all production projections and rebuild the native projects after
the source/dependency/asset steps above:

```powershell
& .\platform\xbox360\build.ps1 -Regenerate -Rebuild
& .\platform\xbox360\test-xenia.ps1 -Seconds 8 -KeepRunning
```

The launcher defaults to physical XInput. `-KeyboardController` is an optional
emulator-only diagnostic mode, not required for normal controller use.

After a successful build, create the small hardware-test package:

```powershell
& .\platform\xbox360\package.ps1
```

Copy `dist/Smash360` intact and launch its `Smash360.xex`. The package includes
both runtime archives, normal diagnostic settings and SHA-256 receipts; it omits
Xenia configuration and PC saves. MSAA defaults to **1x** in both the pinned
interpreter and menu, as requested. Existing settings remain user-owned; the
temporary 4x validation setting was restored to the user's saved 1x setting.

`tools/prepare_application_xdk.py` composes canonical sources into a physical
compiler tree, verifies input hashes, generates both SDK projects and retains
the normal static-library boundary for LUS. All selected application inputs
remain represented. `port_log.c` is compiled once from its corrected projection;
the older corresponding game object is excluded from the direct object list.
The link map selects BattleShip's `n64_stubs.obj` for osSendMesg, osRecvMesg and
osViGetCurrentFramebuffer. LUS os_vi/os_mesg fallback objects are unselected.

The output path is `scratch/application-xdk/native/build/Smash360.xex`.
The first visibly booting XEX is 8,630,272 bytes, SHA-256
`FC19711BA12DA222AE34A6A975937F4AB9CFD06C8C7C007196FFE68459F7071E`.
Cold-build orchestration still requires validation; the incremental combined
build passes. The project derives game/audio/GBI/US HiRes defines from
pinned CMake, and uses the local homebrew title ID `0x534D3601`.
After a successful full build, the build script copies both real host-generated
archives alongside the XEX. `platform/xbox360/test-xenia.ps1` launches that path
using an owned copy of the reference emulator, with evidence under
`scratch/xenia-runs`; it never asserts visible boot itself.

## Architecture and concrete blockers

See `BRINGUP-MAP.md` for A–E ownership and the integration order, and
`CONTRACT-AUDIT.md` for source locations and graphics/resource semantics.

- Preserve PortInit -> PortGameInit -> syMainLoop -> scManagerRunLoop and the
  service-thread coroutine/queue implementation. XDK has the matching fiber
  primitives; nested execution remains to be validated.
- Keep current LUS/Fast3D interfaces. The donor backend predates virtual APIs,
  full 128-bit shader identity plus filter/sRGB, six texture slots, independent
  attachment clears, Z-only writes, and required framebuffer operations.
- Preserve Torch/O2R, Smash reloc factories, pointer tokens, lazy fixes and
  resource lifetime. Do not use SoHPAK or Zelda resource decoders.
- Original LUS native-endian detection selected Little under XDK. The canonical
  compatibility headers now select Big for Xenon; selective asset transformations
  distinguish little-endian archive metadata from big-endian N64 payloads.
- BattleShip currently requests C++20/C11. Its asynchronous resource contracts,
  filesystem/thread primitives and syntax require narrow compatibility work.
  SoH360's existing helpers do not alone solve the newer dependency surface.
- Actual Smash audio synthesis emits native s16 stereo at 32 kHz. Reuse donor
  XAudio2 buffering primitives at that rate, not SoH's 44.1 kHz policy.
- Input must retain ControlDeck and the six-byte Smash pad ABI; reuse donor
  XInput physical-device behavior without copying the older controller class.

Inherited BattleShip deviation: PORT startup skips Nintendo/HAL Startup and
enters OpeningRoom (`decomp/src/sc/scmanager.c:998`). No new boot skip has been
introduced. No new temporary production stubs, fake scenes, disabled gameplay
systems, replacement loops or renderer/asset forks were added.

## Validation and next work

Current hardware validation is summarized at the top and in the final section.
The following entries retain the historical reconstruction and earlier failures.

Verified: exact source acquisition; four clean checkouts; actual host asset
extraction; compiler-only coroutine adaptation; erroneous native-endian
preprocessing; donor/API audit; representative XDK game ABI/endian probes;
host async/environment behavior and XDK object compilation.
Verified additionally: complete combined XDK compile/link and XEX guest entry.
Verified in later run `20260919-215130-181`: Context/services initialization,
actual scheduler boot to OpeningRoom, initial relocation/loading, four frames,
Xenos framebuffer allocation/submission and native XAudio client initialization.
Verified in `20260919-221213-580`: visible real opening rendering, thousands of
frames, opening scene transitions, fighter creation and title-scene entry.
Audio is audible but distorted; text is reported missing. Complete relocation
coverage, menu input, gameplay and hardware behavior remain unverified.
The owned emulator copy was launched. Evidence is in
`scratch/xenia-runs/20260919-204517-642`; native startup logs then XAPI returns 1.
`scratch/xenia-runs/20260919-210055-291` proves real XContent app-data initialization,
LUS configuration/controllers/resource bootstrap and Xbox graphics initialization.
The actual window was observed black. Kernel trace
`scratch/xenia-runs/20260919-210530-064` identifies a later existing-log reopen
failure: mixed `smashsave:\logs/BattleShip.log` returns STATUS_ACCESS_DENIED.
The platform app-path boundary now uses the central filesystem make_preferred
operation, tested against host filesystem behavior and compiled with XDK.
The earlier sandbox launch did not reach guest execution. These early black
windows do not describe the later visibly booting build. No real-hardware test
occurred.

Current detailed evidence: `scratch/xenia-runs/20260919-213159-439` records XEX
SHA-256 `a4b1baf58a27dd161f5e9ab4d4b67598e5d475df13b5104e91516989e44691e2`,
the device/fence snapshot, and successful existing-log reopening. The SDK emits
four ring-buffer kickoffs, all received by Xenia (run `20260919-214006-345`).
Its `host-stacks.txt` and `worker-exception.txt` identify guest logger worker
F8000020 faulting at 8244C414, immediately after backend_flush_ returns into
exception-handler metadata. The GPU worker is suspended by the emulator's
exception path, not shown stuck interpreting a draw. Original EXE/map are
preserved under `scratch/evidence/logger-fallthrough`. GUI ordering and application
thread-0 affinity did not remove the failure. The original GUI order is restored;
donor application affinity is retained. A copied real SoH application passes its
first framebuffer setup in the exact same owned emulator/storage environment
(`20260919-212819-811`); that control is not Smash validation.

`20260919-215130-181/host-stacks.txt` and `audio-exception.txt` locate the next
fault in n_alCSeqNew's track-byte read: invalid address 9FC4D120 equals sequence
base 82B4D120 plus the reversed offset 1D100000. sys/audio.c unconditionally
reversed the 17 native header words after copying the raw BE SBK. The sparse
endian projection now performs that reversal only on LE hosts; event bytes,
audio engine, scheduler and output path are retained. The all-47-sequence test
fails on the original BE policy and passes on both projected BE and LE policies.
The first visible build runs past this fault, but this correction does not fix
the separately reported distorted audio.

`20260919-220438-971` records the controller-connected allocation exception.
Noninvasive guest memory shows mConnectedSDLGamepads at 400224C0 with zero
max_load_factor at +28 and 16,777,216 buckets for one entry. XDK 21256's xhash
move constructor swaps uninitialized bucket metadata into the source. The
controller compiler projection changes that one move construction to normal
default construction plus member swap. Node ownership, refresh and routing stay
unchanged. Run `20260919-221213-580` confirms the corrected path proceeds.

Debugging note: this Xenia revision pauses its GPU worker before printing a
guest exception report. If pause waits do not finish, the visible symptom can
be a GPU fence wait or watchdog hang with no crash report. Noninvasive host
thread stacks exposed the earlier guest exceptions in both cases above. Do
not remove GPU synchronization or alter coroutine scheduling to hide them.

The visual root cause was XDK's mixed-storage bitfield packing: Gpopmtx and
Gsetcolor became 12 bytes, inflating the game's Gfx union to 16 while Fast3D's
F3DGfx stayed 8. Runtime traces show padding interpreted as NOOPs and TEXRECT
reading the wrong continuation packets. The isolated GBI header projection
preserves the N64 field positions and restores 8-byte packets. A PPC production
assertion, actual XDK COFF packet-byte regression, host macro comparison, and
486-TU rebuild validate the compiler boundary; the recording validates the
production path. See `scratch/evidence/user-recording/diagnosis.json` and
`platform/xbox360/game-compat/README.md`.

Next: profile presentation stalls and playback gaps on physical Xbox 360, and
validate an empty-scratch build. Broad graphics changes
stop at the demonstrated visual result. Build artifacts stay under
scratch; runtime dependencies must be copied into Smash360 with provenance.
Xenia logs/storage/caches must also stay under Smash360, leaving references
unchanged. Stop broad work when the real application visibly boots.

Ownership assessment: the demonstrated boot retains Smash -> BattleShip ->
LUS/Fast3D -> Xbox. Smash owns game behavior; BattleShip owns its native adaptation;
the pinned current Fast3D/LUS contracts remain intact; Xbox owns platform behavior.
No alternate production state, loop, renderer or asset system was introduced.
The compiler projection and documented unsupported/temporary capabilities are
explicit deviations, not new game architecture. Visible boot is achieved;
empty-scratch reproducibility and remaining audio issues remain separate.

## Integrated compiler and platform details

| Xbox operation | Owned implementation and donor relationship |
| --- | --- |
| Graphics/presentation/shader cache | `platform/xbox360/graphics`: imported SoH360 Xenos device, surfaces, state, upload, resolve and cache code adapted to the pinned current virtual API and shader identity; current BattleShip/Fast3D shader semantics retained. |
| Controller physical operations | `platform/xbox360/input`: SoH360-derived XInput translation behind actual current ControlDeck/device/mapping classes, with four slots. |
| PCM output | `platform/xbox360/audio`: donor XAudio2 buffer ownership, callbacks and backpressure adapted to current AudioPlayer and Smash's 32 kHz; Smash synthesis retained. |
| Storage/diagnostics/timing | `platform/xbox360/runtime` and graphics donor platform: XContent mounting, worker queues, logging, timing and Xbox startup conventions imported/adapted with local hashes. |
| Threading/scheduler | Actual BattleShip Win32 coroutine code uses XDK fibers. Newer C++ async contracts use narrow Xbox primitives after donor audit; SoH's game loop is not imported. |
| Compiler/CRT/build | `platform/xbox360/cpp-compat`, `game-compat`, `endian`, `tools/prepare-native.ps1`: pinned source projections, central compatibility types and deterministic manifests; XDK compiler/link/XEX tools. |

Temporary deviations/capability limits: fmt 4.1 diagnostic-format compatibility;
unsupported Raphnet transport explicitly reported; temporary startup and bounded
frame/audio timing diagnostics retained for bring-up. Per-frame framebuffer
checkpoint spam was removed. No temporary audio silence, fake
frontend, null game-state replacement or synthetic render path was used.

Shader-cache integration: the inherited game-directory cache path was read-only
in Xenia and would also fail on a physical disc. The existing donor cache and
background writer now use `smashsave:\\smash360-shaders.cache`, mounted before
graphics initialization. Keys, compiler ABI validation, record checksums and
shader behavior are unchanged. First-use compilation remains necessary.
The first run created the cache, and the second logged 199 accepted entries.
An independent BE record parser verified every checksum in a 205-record
snapshot; `scratch/evidence/user-recording/cache-validation.json` records it.
BattleShip's existing bounded PCM capture now writes `cache:\\ssb64_dump.rifx`;
the RIFX header correctly labels Xenon's native big-endian PCM. This diagnostic
does not change submitted audio. Decode its sample bytes explicitly as BE16:
the installed ffmpeg incorrectly reports this RIFX payload as little-endian.

The final composition includes actual Fast3D binary/XML factories, BinaryWriter,
EventDebuggerWindow and all selected BattleShip production translation units.
BinaryWriter's three constructors and both byte orders match original host output
for integer/floating representations, embedded NULs and raw buffers. Native
compilation passes. Fast3D factory algorithms retain their original semantics;
only aggregate/macro initialization and unsupported C++ syntax are lowered.

The current Fast3D API and Smash additions remain intact. The Xbox screenshot
operation reads the backend's existing resolved presentation texture using the
donor's tiled readback operation, explicitly converts ARGB words to RGBA bytes,
then calls BattleShip's pinned stb PNG writer. This is actual framebuffer capture,
not a second rendering path. Compilation/link pass; runtime capture remains
unverified. Optional texture-dump directory creation uses the central filesystem
operation instead of launching a desktop shell.

Partial initialization cleanup now clears a failed Context window, calls the
Fast3D window-manager Destroy only when assigned, and reports texture-buffer
allocation failure. Normal initialization and teardown order remain unchanged.
Cold generation is provided by `tools/prepare-native.ps1` and `build.ps1 -Regenerate`;
it has not yet been validated end-to-end from an empty scratch directory.

## Resolution/MSAA lifetime fix and bounded optimization

The resolution-slider freeze in run `20260919-232429-910` was not evidence of
unsupported tiled rendering. Noninvasive host stacks located a guest CPU access
violation in JSON destruction while saving the setting. The invalid tree-node
words occupied the offsets used by an XDK texture's fence fields; the log also
recorded an invalid GPU upload address. This was consistent with a released
texture header being reused as a configuration allocation, not a reason to
rewrite JSON or remove GPU synchronization.

The source-level lifetime defect was in the Xbox adapter: BattleShip can resize
the framebuffer during StartFrame and then present a held VI without composing
a new game frame. Its cached ImTextureID still references the previously
published texture, while the inherited framebuffer resize drops that texture's
ownership. The narrow `tools/prepare_graphics_xdk.py` projection now retains one
reference to the published image until the next distinct image is published,
then retires the old reference through SoH360's existing deferred-release queue.
Shutdown releases the retained image after GPU idle. BattleShip's held-frame
behavior, scheduler, GUI order, configuration code and MSAA algorithms are intact.

The corrected XEX passes the native build, real scheduler/VI/message ownership
audit, and PPC logger regression. In run `20260919-233953-521`, the physical
controller changed the game framebuffer from 1523x856 at native 1x to native
4x and 2x, resized through 1190x669 to 1318x741, and returned to native 1x at
1305x734. Rendering/timing reports continued after these changes; the earlier
invalid-upload message did not recur, and the user confirmed both controls work.
The inherited backend normalizes requested samples to native 1x/2x/4x: the
desktop slider's requested 3 and 6 correspond to native 2 and 4, respectively.
Its displayed values are not additional native sample modes. High resolution
and MSAA still increase EDRAM tile work; this fix makes no performance promise.

The native renderer also now reuses unchanged c8-c13 texture-binding constants,
using the same aligned, bit-exact VMX comparison policy as SoH360's existing
constant cache. All six current Fast3D binding records and their semantics remain
intact; framebuffer/GUI/state changes invalidate the cache. The production
verification run `20260919-232310-259` used XEX
`144A776A8029C8DD5CEF8E9C97F03225CE5114A15B5E3ED794F5F3BBAF749953`:
198,990 of 277,165 uploads were avoided (71.79%) over 15 five-second reporting
windows. D3D constant readback checked every suppressed upload, with no mismatch.
This is reduced SDK upload work, not a measured FPS improvement on hardware.
Evidence: `scratch/evidence/cursor-cache/results.json` and `verification.log`.
The lifetime-fix build retains this cache unchanged.

`SMASH360_VERIFY_NATIVE_REUSE=1` enables intrusive state/readback verification;
`SMASH360_DISABLE_BINDING_CACHE=1` disables this added cache for comparison.
Both are disabled in the normal build's `smash360.env`. No audio-engine or
emulator timing workaround accompanies the optimization. Audio underruns and
presentation stalls remain observable in the resolution/MSAA retest.

## Pre-hardware efficiency pass (2026-09-20)

The Xbox adapter now avoids restoring attachments that an immediate full-target
clear will discard. This restores SoH360's existing discard-before-clear behavior
while preserving BattleShip's newer independent color/depth contract. For an
inactive framebuffer, depth-only clear retains all color fragments and skips old
depth restoration; clearing both attachments skips the restore quad entirely.
Color-only clear with a depth attachment retains the original restore path so
depth survives. Live-frame and region-clear behavior remains unchanged. Smash's
cross-frame color persistence is retained. No game/interpreter changes were made.

The regression executes the actual projected Clear and BeginFramebuffer code
against a host SDK-operation model. Across 72 combinations of 1x/2x/4x samples,
tiling, live/inactive state, attachments and clear flags, the old code performed
42 overwritten restore draws and 28 overwritten depth reads. The new code performs
zero of each with identical modeled attachment contents. All four graphics
preparation/clear tests pass. This model is not a GPU pixel-equivalence proof.

Production runs `20260919-235422-249` (1x) and `20260919-235603-170` (4x) used
clear-only XEX `F38AA84CD5E2B266BD999023A0C235D5815BF1B4DF7C24BF2499A2E238373F13`.
Real opening sequences rendered in both; screenshots and logs are preserved in
`scratch/evidence/clear-reuse`. The 1x run avoided 4,724 restore draws and 4,764
depth-sample restorations across 19 reporting windows; the 4x run avoided 1,903
of each across 17 windows. These are operation counts, not controlled timing or
hardware FPS measurements. Native 4x at 1305x734 used four EDRAM tiles and was
slow in Xenia. The user's `2026-09-19 23-56-13.mp4` records that run. The diagnostic
switch `SMASH360_DISABLE_CLEAR_REUSE=1` restores the prior clear behavior for A/B
checks; it is off by default and absent from the normal hardware configuration.

Input also now shares a single four-slot physical sample between ImGui NewFrame
and the same presentation's GUI device handler, following SoH's sampled-input
sharing. This eliminates 1-4 duplicate XInput state reads per presentation.
The sample can be consumed only once; a missing sample or intervening ordinary
pump triggers a fresh poll. Window-event and game-controller reads still poll
independently. The actual manager/physical bridge host tests cover freshness,
topology, disconnection, mapping, rumble expiry and the six-byte game controller
ABI. Native bridge and GUI-frame sources compile with XDK. This is not a change
to gameplay input cadence or a millisecond-based input cache.

Further optimization should begin with physical-console measurements. Older
SoH CPU/Fast3D optimizations require comparison with Smash's current semantics
before import. Xenia Present time alone does not identify a physical Xbox CPU
or GPU bottleneck. Audio underruns, hardware validation and empty-scratch build
validation remain open. The changes preserve the Smash / BattleShip /
Fast3D-libultraship / Xbox ownership boundaries.

## First hardware launch: storage-selector startup contract

The EF235E05 package launched on the user's Xbox 360, displayed storage selection,
then returned to Aurora before a device could be chosen. The user was signed into
controller 1. The supplied `smash360.log` records two identical clean startup exits:
`save device selection error=1223 device=0`, followed by normal diagnostic-worker
shutdown. Error 1223 is ERROR_CANCELLED. Storage had not mounted and the game had
not initialized; this evidence does not indicate a renderer crash or save damage.
The original hardware log and failed-package hashes are preserved.

The local XDK 21256.3 Screen Displays Overview (`profiles_display_information_overview.htm`)
requires Direct3D before XShow functions and continued Swap/Present while waiting
for XHasOverlappedIoCompleted. The inherited storage code instead opened the
selector before device creation and blocked its presentation thread in
XGetOverlappedResult(TRUE). The copied auto-reset event also did not meet that
blocking wait's documented manual-reset event contract. SoH360's current config
read path can reach the same inherited sequence; the references were not edited.

The owned projection now separates creation of the existing donor device from
the rest of renderer initialization. Storage ensures that device exists, then
uses its native presentation target to service the system overlay until selection
completes. Fast3D subsequently captures presentation surfaces, initializes its
normal restore resources/state and creates framebuffer zero on the same device.
No alternate game loop, game frame, resource system or frontend is introduced.
Device and pending-operation lifetimes are retained through completion/cancellation;
startup shutdown also releases an early device when no Context was created.
XContent container identity, user slot, config and SRAM formats remain unchanged.

The actual projected MountSave host contract check covers delayed selection,
immediate completion, cancellation, presentation failure and repeat mount calls.
All five graphics/storage tests and the native XDK build pass, including real
scheduler/message ownership and the PPC logger regression. The new Xenia run
records `initial=997 result=0 ... presents=3`, then storage mount and normal game
rendering; one device-creation log confirms reuse. A diagnostic-file flush warning
also occurred in that emulator run; debugger logging continued. These results
do not replace the requested physical-console retry.

That retry failed: F87F3A6B logged `result=1223 extended=000004c7`, profile
slot zero still signed in, after 42 successful Presents / 726.2ms. The user saw
the popup close before device choices appeared and confirmed SoH360 selection
works on the same console. The new log is preserved as
`scratch/evidence/hardware-storage-ui/hardware-retry-F87F3A6B.log`. The D3D/wait
contract correction is valid but is not the complete hardware fix. No container
mount or game initialization occurred; the return to Aurora is our clean exit
on failed storage preparation.

Comparison with the installed XDK XContent sample and SoH found no evidenced
title-resource/privilege defect: all use a title ID without requiring SPA/XDBF
resources for this selector. XDK documentation recommends XOnlineStartup, which
neither current native project calls; selector-specific docs do not establish
that omission as the cause of cancellation, and it also exists in working SoH.
It has not been added as a speculative fix.

A temporary, bounded `StorageSelectorTrace` now records system UI, sign-in,
storage and input notifications, changed input/profile states for all four slots,
and available physical memory around the actual pending selector. It follows
the donor's independent XNOTIFY_SYSTEM listener pattern. The system may mask
XInput while the Guide owns input, so a neutral in-UI sample is not conclusive.
The trace changes no selection policy, does not consume keystrokes, and retains
the real XContent mount/config/SRAM path. This build is a diagnostic step; physical
boot remains blocked pending evidence of why XAM returns cancellation.

The traced build is SHA256
`759DE84FA3B50CCE7508FFB3075DB220E72288163CBEB437A103E0C94CF43342`, packaged at
`dist/Smash360/Smash360.xex`. Five graphics/storage host checks, the XDK build,
production-symbol audit and PPC logger check pass. Xenia run
`20260920-014224-497` selected storage successfully after three Presents, mounted
`smashsave:\`, and rendered the genuine opening sequence (Mario/Samus screenshot
saved). Evidence is in
`scratch/evidence/hardware-storage-ui/selector-trace-759DE84F`. Hardware retry is
pending. The XEX alone needs replacing; assets and normal configuration are unchanged.

The user's game:/cache:/ hypothesis was checked against the pre-selector path:
the hardware environment file read from `game:\` succeeded, logical-cwd setup
validated that directory, and logging uses `game:\` with `cache:\` only as a
nonfatal fallback. Config/SRAM/shader-cache access requires the subsequent
`smashsave:\` mount, which was never reached. The trace also probes both root
directories using read-only GetFileAttributes calls. A missing `cache:\` is not
treated as a startup failure or permission to change the save architecture.

The physical 759DE84F trace confirmed `game:\` exists and `cache:\` is absent
(error 2). It also recorded 482,095,104 available physical bytes, connected
controller zero with neutral buttons, and two XN_SYS_SIGNINCHANGED notifications
while the selector was pending (346.3ms and 529.2ms after the trace began).
Cancellation followed after 57 Presents / 969.3ms. The queried profile remained
signed in throughout. See `selector-trace-759DE84F/hardware-signin-cancel.log`.
These observations support a startup sign-in/UI interaction; they do not prove
XAM's internal reason for cancelling. The SDK notes notifications can be coalesced
or reordered, and their sign-in parameter must not substitute for a state query.

The storage projection now makes one bounded recovery attempt when a pending
selector returns ERROR_CANCELLED and a sign-in notification was observed during
that pending interval. It keeps presenting until the old UI hides (five-second
upper bound), then verifies the original stable offline profile using
XUserGetSigninInfo with XUSER_GET_SIGNIN_INFO_OFFLINE_XUID_ONLY. Default
XUserGetXUID is deliberately not used for identity comparisons because it changes
between online/offline state. An observed B press, any observed profile mismatch,
unavailable identity, newly visible UI, or Present failure vetoes recovery.
Those vetoes are rechecked immediately before reopening. Notifications first seen
after completion cannot authorize retry. Each request has fresh XOVERLAPPED and
event storage, with the previous request completed before release/reuse.

This is a temporary recovery heuristic based on the captured hardware sequence.
Intentional cancellation coincident with a sign-in notification can be
indistinguishable while XAM masks controller input, so retry is limited to one.
It neither selects storage for the user nor permits game startup without the
real XContent mount. Repeated cancellation and ordinary cancellation still fail
cleanly. The host regression executes the actual projected MountSave, and covers
the interrupted same-profile recovery plus the cancellation, identity, timeout,
presentation and late-notification vetoes. The first physical result follows.

## First successful physical-console gameplay (2026-09-20)

Build F0F4F3DC passed the native build/production ownership/logger checks and all
five graphics/storage host tests before shipment. In the user's appended log,
the older revision-1 failure precedes the new revision-2 launch. The new launch
records first-attempt cancellation after 1,235.9ms with two sign-in events and no
observed profile change or cancel input. The old UI hides at 1,627.1ms from trace
start; the second selector succeeds after 1,579.7ms and the real XContent mount
completes. No cache partition was created or required. The recording then proves
playable Hyrule Castle, transition, and Yoshi-team gameplay on the console.

The successful launch contains 30 approximately five-second timing windows:
7,672 presentations over 150.319 seconds, or 51.04 FPS across this mixed run.
The last eight windows average 44.28 FPS (42.74-47.25 per window), with weighted
game-side time 4.12ms, rendering interval 18.40ms, and Present call time 0.066ms.
The rendering interval includes Fast3D, native backend CPU work and potential
GPU waits; it is not an isolated CPU or GPU measurement. The video overlay also
shows roughly 40-50 FPS in gameplay. This is a single first-cache-building run,
not a controlled benchmark or a 60 FPS claim.

The audio queue reports 230 empty submissions/rebuffer recoveries across the
30 reporting windows, zero XAudio-reported engine glitches, and zero PCM-buffer
storage wait. The complete shader-creation timer has 76 logged hitches over 8ms (83.2ms maximum),
and 110 background shader-cache writes report success. Compilation accounts for
some initial stalls; sustained late-window rendering cost still exceeds the
60Hz frame budget. Audio is therefore not considered fixed. Shader-cache
persistence was subsequently verified below; config and SRAM persistence remain
to be checked independently.

Evidence includes the supplied complete log, its hash, recording hash/path,
contact sheet, full-resolution Yoshi gameplay frame, timing summary, XEX/EXE/map,
and package/link receipts in `scratch/evidence/hardware-boot-F0F4F3DC`. The video
and log have no common absolute frame timestamps, so individual log windows are
not asserted to correspond to specific video scenes.

The warm-cache console follow-up is recorded below. Next, measure Fast3D CPU work,
backend submission and GPU synchronization separately using the existing SoH
profiling facilities where their contracts match. Preserve the current known
bootable build before changing performance behavior. No production-code change
was made while reviewing this successful hardware receipt.

Ownership still holds: Smash owns gameplay; BattleShip owns its native adaptation
and scheduler; Fast3D/libultraship keep their normal interfaces; Xbox owns native
display/input/audio/storage and this startup recovery. The known temporary
deviation is the bounded sign-in-correlated selector retry, with the limitations
documented above. There is no alternate renderer, asset loader or game path.

## Hardware warm-cache follow-up (2026-09-20 02:08)

The next supplied log confirms persistent loading of 133 compiled shader entries
(367,960 bytes) from `smashsave:\smash360-shaders.cache`, with no new background
shader-cache write records. The optional `cache:\` partition remains absent.
The same guarded storage recovery succeeds again: first selector cancelled with
two pending sign-in events, then UI-hide and the same-profile second request
successfully mount `smashsave:\`.

The 76 shader keys with logged creation hitches in both runs have a median
creation time of 35.46ms cold versus 15.39ms warm, and summed logged durations of
2,849.60ms versus 1,209.41ms. The `compile_create_ms` field starts before the real
BattleShip/Prism shader generation and Xbox source lowering, then includes cache
lookups/compilation and native shader/declaration creation. It does not identify
individual compiler invocations. Cache persistence/loading is proven; this run
does not emit a per-lookup hit/miss summary.

Sustained performance remains limited: 4,773 presentations over 100.288 seconds
(47.59 FPS across this different mix of scenes), with the last 40.116 seconds at
44.07 FPS. The latter windows average 4.05ms game-side work, 18.60ms rendering
interval, and 0.043ms in Present. They are qualitatively similar to the cold
run's slower windows; these are not controlled, frame-matched comparisons.
The audio queue reports 203 empty submissions/recoveries and zero XAudio engine
glitches in 20 reporting windows. Warming the shader cache does not resolve the
sustained rendering cost or associated playback starvation.

The exact log and calculated summary are preserved in
`scratch/evidence/hardware-warm-cache-F0F4F3DC`. The verified XEX is unchanged.
Next profiling should separate interpreter work, backend submission, texture
uploads and GPU synchronization using the existing SoH facilities where their
contracts match, before selecting another optimization.

## Granular stage/work profiling (2026-09-20)

Diagnostic XEX SHA256: `0866F186CDFAD6788D9D9ED5BF7308B9DACB1A67E3D9D6827AF37D591484C2CB`.
Hardware package: `dist/Smash360/Smash360.xex`. Assets are unchanged; MSAA still
uses the existing 1x default. The F0F4F3DC hardware build remains frozen in its
original evidence directory for comparison.

Retained the SoH donor native performance scopes and adapted its thread-local
PPC time-base collection/background report transport. Added nested self-time
accounting and exact source-projection observers around the real BattleShip
interpreter, command dispatch, walk-bounds checks, GBI callback, matrix/vertex/
triangle work, texture content checks/cache/import, shader generation/lowering,
and LUS GUI. Native timing distinguishes game draw submission, resource creation,
texture/depth locks, deferred releases, framebuffer stores/restores, EndTiling,
and existing explicit idle waits. No extra GPU synchronization is introduced.

Each five-second report includes normalized work counts, existing native state
suppression/upload-reuse counters, shader cache hit/miss/compiler counts, current
published framebuffer size/MSAA, longest individual calls and observer/diagnostic
transport overhead. Inclusive sections overlap; self time excludes instrumented
children but includes uninstrumented descendants and waits. These are wall-time
measurements, not isolated GPU timing. Full schema, provenance, limitations and
hardware comparison procedure: `platform/xbox360/runtime/PROFILING.md`.

Validation: six host graphics/storage/profiler tests passed; actual XDK graphics
objects and shader fixture compiled; production XEX/link and PPC logger checks
passed. Xenia run `20260920-023415-795` emitted five complete reports through real
opening-sequence frames. Their summed self time agrees with the broad rendering
interval within the expected small boundary/rounding difference. The registered
GBI callback and walk-bounds checks actually execute, and the warm binary shader
cache reports hits with no compiler calls. These timings do not establish console
bottlenecks. In this run the flat-scope observer estimate ranged roughly
0.30-1.13ms per frame: diagnostic perturbation is measurable and must be considered.
Run `20260920-023524-507` verifies `SMASH360_PROFILE=0`: schema reports disabled,
broad frame logging continues, and no granular report is emitted. Both runs use
the same XEX; no hardware performance improvement is claimed.

The user's screenshot `codex-clipboard-34029285-564d-4d83-8876-fce285d6184d.png`
shows remaining intro corruption around the room wall/curtain. Preserve this as
an open graphics-correctness issue; prior positive gameplay observations were
not exhaustive correctness validation. The profiling additions change no game,
cache verification, render-state, shader equation, asset or scheduler behavior.

## RDP initialization correction (2026-09-20)

The user localized intermittent missing room geometry to the first opening scene
in Xenia, before the lights turn on; fighter selection varies naturally at launch.
The issue was reproduced and investigated without changing the chosen fighters,
game state or command stream. A strict-LESS depth experiment worsened the intro
and was reverted. Both Xenia ROV and RTV modes could show an intact room; neither
was established as the cause or used as a workaround. Those comparison captures
are in `scratch/evidence/intro-depth-compare`.

The decisive contract defect is in XDK initialization of BattleShip's `RDP`:
modern `new RDP()` zero-initializes the aggregate and constructs its nested
metadata. The linked Xbox binary instead allocated 1064 bytes and constructed
only the three metadata members, leaving the enclosing scalars indeterminate.
Its neighboring RSP allocation did perform the required zeroing. SoH's older
Fast3D has static RDP storage, which is already zero-initialized.
The failing binary and disassembly are frozen in `scratch/evidence/rdp-value-init`.
In baseline run `20260920-030805-192`, all traced shader draws unexpectedly
included GRAYSCALE (bit 0x80), including framebuffer fills; the game source has
no matching grayscale commands. This is direct evidence of incorrect state,
not proof that every visual symptom has this one cause.

Only the pinned interpreter's `new RDP()` expression is projected to the helper
`platform/xbox360/cpp-compat/fast3d/rdp_value_init.h`. It zeroes raw allocated
storage **before** constructing the real RDP, preserving metadata defaults,
shared_ptr lifetimes and ordinary-delete ownership. Constructor failure releases
the allocation and rethrows. No live object is memset, and no game-specific
renderer condition, replacement state or shader workaround is added.

Validation:

- The new linked-PPC regression fails on the frozen pre-fix EXE and passes on
  the correction. It proves exact allocation size/pointer and zero-before-real-
  constructor order; `build.ps1` now runs it after every application link.
- Existing full-header tests now poison RDP allocation memory and check every
  meaningful scalar/array/nested field, empty resource owners, scales and ordinary
  deletion. Actual upstream and adapted headers produce identical host results;
  the same tests compile with XDK. Four projection tests and six graphics tests
  pass. Existing compiler warnings remain; no build/test errors occurred.
- The production startup log reports zero grayscale/masks/blends/modes/depth and
  metadata scales 1/1. Corrected traced run `20260920-031916-495` has no unexpected
  grayscale flag, including the fill draws (7 floats/vertex versus baseline 11).
- Four captured starts show the intact dark room: Yoshi/DK, Pikachu/Mario,
  Samus/Kirby, then Yoshi/DK again in final run `20260920-032336-149`. Final XEX
  SHA256 is `8B6F64BB35CC53948BF83822008AE79185D187171516F4BDC2077EBDEB9537F2`.
  These samples do not exhaust all character choices or prove physical-console
  correctness. Link-specific observations remain to be retested.

The temporary per-draw depth observer is removed from the final build; its
source, diagnostic binary and output are preserved with the evidence. The
granular profiler remains enabled by default and can be disabled with
`SMASH360_PROFILE=0`. MSAA remains 1x by default; assets are unchanged.
Next: recheck the reported intro on console, then collect light/busy fight logs
to locate sustained frame cost. No hardware speedup is claimed from Xenia data.
Smash still owns game behavior, BattleShip the native adaptation, Fast3D/LUS
their normal contracts, and Xbox the platform/compiler compatibility boundary.

## First granular physical-console profile (2026-09-20)

The supplied log at `D:/Projects/SoH360/scratch/hardware/SoH360-normal-9eda7559/smash360.log`
was inspected read-only and preserved under `scratch/evidence/hardware-profile-20260920`.
It contains two appended launches; the second contains the corrected RDP startup
values and 33 complete profiling windows over 165.368 seconds at 1280x720 / 1x MSAA.
The exact XEX hash is absent, so the log establishes execution of the correction,
not binary identity or visual correctness. Storage's existing retry succeeds.

Slower post-startup windows average 16.49 ms rendering and 3.58 ms game/logic.
The principal rendering costs are command-step self time 8.74 ms, bounds checks
2.18 ms and triangle-processing self time 2.01 ms. Native draw handling plus
submission is 0.40 ms; texture uploads are 0.007 ms. Profile observer overhead is
estimated at 0.70 ms/frame. These calling-thread scopes strongly prioritize CPU
interpreter work for investigation; they do not independently measure the GPU.

Two sustained stretches average 50.00 and 44.67 FPS, with command counts rising
from 3447 to 4065 per frame. The log does not identify scenes or fighter counts.
Only two shaders compile in the newer launch, none in the selected slow windows.
Its audio reports 286 empty submissions/recoveries and zero engine glitches.
Next targets are handler-family costs, ownership/reloc lookup overhead and
bounds-cache generation/read behavior. Preserve the real scheduler callback
and range safety checks. Full selection criteria, values and limitations are
in the evidence directory's `ANALYSIS.md`, `windows.json` and `summary.json`.

## Interpreter attribution and native-endian runtime repair (2026-09-20)

Optional `SMASH360_PROFILE_DETAIL=1` now separates dispatch opcodes, temporary
weak-owner acquisition, reloc lookup/fixup, and bounds generation/scan costs.
It preserves the real calls, memory ordering, ownership lifetimes and scheduler
callback. Schema 2 prints the eight busiest opcodes plus aggregate remainder;
all 256 slots contribute to totals. Detail defaults off in code, but the current
hardware diagnostic package enables it explicitly through `smash360.env`.
`SMASH360_PROFILE=0` disables both profiling levels. Detail adds measurable
overhead; use comparable settings and a disabled-profile control.

The detailed baseline XEX `212895A3BD59B4744DD77CDBB85C392C8CD7E98BAF42C2A853FBEA6CA4E6CCDF`
ran the real intro in Xenia, with 1.24-1.277 ms/frame runtime texture repair self
time in three sustained windows. These are emulator timings, not console
predictions. Source tracing establishes the redundant work: Xbox never applies
the LE blanket blob swap, and already treats these inverse byte/halfword repairs
as identities, yet the runtime functions continued range lookup and word/vertex
hash bookkeeping every time. Shared-container consumers were audited before
changing the path. Other sprite conversions, real deswizzle, relocation tokens,
protected ranges, Fast3D texture loads and actual vertex processing are preserved.

Only the owned `tools/prepare_endian_xdk.py` projection changes behavior: runtime
texture/vertex endian repair returns immediately on BE unless existing stage
audit/texture log/texture dump flags request its original body. This also removes
the ordinary first-512 texture and first-64 clamp diagnostics from the fast path.
No game or reference source is edited. No SoH game semantics are substituted.
Bounds UNKNOWN caching, acquire atomics and weak-owner behavior remain unchanged
as separate follow-up leads; no broad interpreter optimization was attempted.

Validation: extracted real functions failed the new no-redundant-scan regression
before the correction and passed afterward in BE and LE modes. Tests cover
overlapping palettes/vertices, unchanged BE bytes/live tokens, all three asset
diagnostic modes, real sprite deswizzle/idempotency, synthetic sprites and heap
reuse. Three overlay integrity tests pass. Full XDK build, native link receipt,
PPC logger and RDP initialization guards pass; linked disassembly confirms early
return before range lookup/word tracking with diagnostics disabled.

Current package: `dist/Smash360/Smash360.xex`, SHA256
`31AAB5727137E9C166B78CB9449E74608C0729EE16576FA2CD2B3F7A8F7FB437`.
Reproduce with `python -B tools/prepare_endian_xdk.py`,
`python -B tools/prepare_port_xdk.py --prepare-only`,
`platform/xbox360/build.ps1`, then `platform/xbox360/package.ps1 -ProfileDetail`.
Full clean preparation remains documented above. Assets and native 1x MSAA
default are unchanged. Evidence: `scratch/evidence/interpreter-detail`, build
log `scratch/runtime-fixup-build.log`, profiling guide under runtime/PROFILING.md.

The corrected binary has not yet been run or visually validated. No computer
control was used after the user prohibited it. Next: physical-console validation
of menus/intro/gameplay, comparable light/busy fight logs, then profiler-disabled
comparison. No hardware speedup is claimed. Smash owns game behavior, BattleShip
its native adaptation, Fast3D/LUS their contracts, and Xbox its platform/compiler
and native-endian compatibility; these boundaries remain intact.

## Console feedback after endian repair correction (2026-09-20)

The next supplied console log is preserved in
`scratch/evidence/hardware-endian-fix-20260920` with SHA256
`639b00a258934d10b011a26b1dc9f0c6e937a4c1de85f7ccd2580d6c99f9ff2d`.
Its successful second launch has 50 complete schema-2/detail-enabled windows,
250.243 seconds at 1280x720/1x MSAA: 58.355 FPS overall. Runtime texture and
vertex repair together average 0.0317 ms/frame, supporting the intended fast
path on hardware. Binary hash and scene identity are not logged; visual
correctness is not established from timing records.

Heavier windows 15-27 average 56.651 FPS / 13.198 ms rendering / 4,351 commands,
while windows 32-44 average 60.089 FPS for 65 seconds. The heavier block spends
2.053 ms in locked bounds scans and 0.953 ms in generation acquire; 2,568 misses
scan 102,707 entries each frame, almost all returning UNKNOWN. This is now a
console-confirmed investigation target. Detailed-profiler observer cost is
estimated at 1.792 ms/frame in that block. Preserve range safety and avoid
uncontrolled old/new FPS comparisons. Audio still has 71 empty submissions/
recoveries in 51 reports, with zero engine glitches. Full accounting and limits
are in the evidence directory's ANALYSIS.md and summary.json. No code, package
configuration or emulator state changed during this review.

## UNKNOWN bounds scan correction (2026-09-20)

The owned Xbox projection now caches a proved UNKNOWN address interval, in
addition to BattleShip's existing positive cache. A locked scan computes the
gap outside all registered ranges and their 64 KiB walked-past windows. Only
the final UNKNOWN result publishes it. Each hit still requires the unchanged
64-bit generation acquire, so register/resize/unregister invalidates the cache.
Positive overlap precedence, unsigned endpoint semantics, null handling, real
callbacks, writer synchronization and the original slow scan remain intact.
No safety check is disabled and no game-address heuristic is used.

Implementation: `tools/bounds_cache_projection.py`, composed through
`tools/prepare_port_xdk.py`, with helper `cpp-compat/port/bounds_gap.h` under
the owned Xbox boundary. `bounds_unknown_hits` identifies the saved scans in
the existing diagnostic stream. The generation atomic itself is unchanged.

Validation: the actual-source ILP32 regression first failed on repeated scans,
then passed with the cache; original/projected classification comparisons cover
over 450,000 addresses with overlaps, endpoint wrap, invalidation and mutations.
2,000 writer/reader handshakes verify cross-thread TLS invalidation. Six existing
graphics tests pass. Full XDK/link/PPC logger/RDP guards pass. Linked PPC confirms
the new hit path returns before the mutex. Evidence and limitations are saved
in `scratch/evidence/bounds-unknown-cache/ANALYSIS.md`.

Current `dist/Smash360/Smash360.xex` SHA256:
`D59904A90E5DC8BD6426B42B14CC797B5AE89386C0512ADA069A1D1B62E4335A`.
Rebuild with `python -B tools/prepare_port_xdk.py --prepare-only`, then
`platform/xbox360/build.ps1` and `platform/xbox360/package.ps1 -ProfileDetail`.
Detailed profiling remains enabled for the next console comparison, with 1x
MSAA default and unchanged assets. No computer control or fresh runtime launch
was performed. Console execution, scan-hit rates, performance and visual
regression confirmation remain pending; this build has no measured speedup yet.

## Console cache validation and Yoshi intro stress case (2026-09-20)

The next supplied log from `D:/Projects/smash360.log` appends one new launch to
the previous exact log. Latest-launch evidence is preserved under
`scratch/evidence/hardware-bounds-cache-20260920`. UNKNOWN caching executes on
hardware: locked scans average 0.0314 ms/frame; the later higher-command block
averages 0.0415 ms / 997 range visits, compared with the prior heavier block's
2.053 ms / 102,707 visits. Different scenes preclude a precise speedup claim.

The isolated 39.97/33.31 FPS dip is consistent with the user's Yoshi prematch
report, although scene IDs are not logged. The worst window submits 9,886
commands/frame and takes 23.242 ms CPU rendering: triangle self 5.348 ms,
generation acquire 2.225 ms, owner acquisition 1.722 ms, vertex processing
1.693 ms. Bounds scanning is only 0.096 ms; shaders compile zero times. The
decomp intentionally constructs 18 Yoshi fighter objects on this screen.
The detail observer estimate is 3.813 ms/frame, so instrumentation materially
affects the stress case. Preserve those fighters and optimize common operations.
After the dip, 160 seconds average 59.784 FPS. Audio underruns remain (42 in
44 audio reports). No further code/configuration change was made for this review.

## Acquire and dispatch owner CPU corrections (2026-09-20)

Two shared overheads measured on the Yoshi intro are addressed at owned Xbox
boundaries. `cpp-compat/port/atomic.h` now uses the XDK acquire interlocked API
for acquire loads, retaining atomic width and ordering while replacing two
full barriers with one acquire barrier. Other operations retain prior fences.
The bounds registry, invalidation protocol and classifier are unchanged.

`tools/dispatch_owner_projection.py` and `cpp-compat/fast3d/dispatch_owner.h`
retain one strong reference to the selected interpreter during the existing
command walk. The 90 temporary handler lookups borrow it, avoiding per-command
weak acquire/release. Scope exit restores TLS, and GfxSetInstance invalidates
all saved scopes; outside-dispatch/invalidated calls use the original fallback.
Window lifetime and real command dispatch remain intact. RunGuiOnly, game
behavior, all 18 Yoshi intro objects, triangle semantics and assets are unchanged.

Tests pass for acquire publication, exact PPC fence paths, scoped ownership,
invalidation/exception/TLS cases and original/projected bounds classification.
Full XDK/native link/logger/RDP guards pass. Linked bounds and triangle-handler
disassembly confirms the lighter acquisition and borrowed-owner production paths.
Evidence: `scratch/evidence/dispatch-acquire/ANALYSIS.md`. No computer control
or runtime launch was used; console confirmation of the latest changes remains
required. Triangle-processing cost and profiler overhead are not claimed solved.

Current package XEX SHA256:
`DE87CABD4679BC366B0CB3640508F955D62D52AD15B3E1FD7E7FD0DEB27D0B1D`.
Incremental reproduction: prepare_fast3d_xdk.py, prepare_port_xdk.py --prepare-only,
platform/xbox360/build.ps1, then package.ps1 -ProfileDetail. Detailed profiling
remains enabled for comparable logs; SMASH360_PROFILE=0 gives a disabled control.
No hardware speedup is claimed before retesting the Yoshi prematch screen.

## Persistent Yoshi slowdown: exact projection reuse (2026-09-20)

Latest console log still reaches only 31.49 FPS during the fully populated
intro, with 14,359 commands and 4,185 triangle requests per frame. The previous
owner/acquire changes did reduce their per-call costs (205.9 to 46.4 ns and
207.35 to 89.74 ns respectively); this longer-held scene has more work than
the preceding capture. Triangle self time remains 7.642 ms/frame. There are
no texture uploads or shader compilations in that window. The detailed
observer estimates 5.540 ms/frame across 100,119 scopes; this materially
perturbs the scene. Evidence is preserved in
`scratch/evidence/hardware-dispatch-acquire-20260920`.

The owned Fast3D generator now skips draw-diagnostic UV range preparation
when its existing diagnostic flag is off. It also adapts SoH360's scalar
projection cache: `tools/cull_projection.py` and
`platform/xbox360/cpp-compat/fast3d/cull_projection.h`. Raw x/y/w keys detect
vertex mutations at both culling and BattleShip's later RCP screen-area read.
No reciprocal approximation, altered area/cull arithmetic, model omission,
replacement scheduler or game-specific renderer behavior was introduced.
All 18 Yoshi objects remain. No upstream/reference source was modified.

Seven Fast3D tests pass, including 1,600,000 original/projected cull decisions
and 196,625 area/accumulation comparisons from extracted BattleShip source.
Coverage includes repeated indices, rectangle slots, signed zero, nonfinite
inputs and changes between cull and area evaluation. Full XDK build and
linked logger/RDP guards pass. PPC inspection confirms cache hits skip scalar
divides, direct integer key loads avoid FP spills, and disabled diagnostics
skip preparation. Evidence: `scratch/evidence/projection-reuse/ANALYSIS.md`.

Reproduce with `python -B tools/prepare_fast3d_xdk.py`, then
`platform/xbox360/build.ps1` and `platform/xbox360/package.ps1 -ProfileDisabled`.
Current XEX: `dist/Smash360/Smash360.xex`, SHA256
`43D209D20267D8A274A842EC48047AAFF29FA51A89A6A91772EB9667CC27F435`.
This package explicitly disables granular profiling in `smash360.env` while
keeping broad frame/audio logs. Copy that file with the XEX. MSAA remains 1x
by default; assets are unchanged. Configuration and code both changed, so
the next result cannot isolate individual optimization gains.

No new emulator/hardware run or computer control was performed. Physical
performance and visual confirmation remain pending; the Yoshi slowdown is
not declared resolved. Smash, BattleShip, Fast3D and Xbox ownership boundaries
remain intact. Hold the full Yoshi intro for about 20 seconds on console to
measure the runtime-disabled profiling control and check for visual changes.

## Console result with profiling disabled (2026-09-20)

The user reports about seven FPS improvement. Latest log confirms
`enabled=0 detail=0` and native 1x MSAA. Across 39 complete five-second windows,
weighted FPS is 58.33. The slowest window is 40.97 FPS (205/5.004 s), with
3.683 ms logic, 19.277 ms render and 1.451 ms present. The next nine windows
run at 59.75-60.15 FPS. The heavy intro remains below target; its render
interval alone exceeds a 60 Hz frame budget.

The prior worst window was 31.49 FPS / 28.735 ms render, but these windows are
not scene-aligned and the new log has no detailed work counts. Both code and
profiling changed, so this is not an isolated projection-cache speedup claim.
The five-second minimum can also mix scene transitions. Evidence and comparison
limits: `scratch/evidence/hardware-projection-reuse-20260920/ANALYSIS.md`.
No further implementation or package changes were made during this log review.

## SoH color conversion and vertex packing reuse (2026-09-20)

The next owned projection imports SoH's exact 256-entry byte-color quotient
table and adapts its local output cursor to BattleShip's real triangle packing
loop. This removes per-channel integer-to-FP conversion/division and repeated
buffer counter updates without changing the emitted vertex stream. The 17
normalization expressions and 25 writes are explicitly counted by
`tools/vertex_packing_projection.py`; the standalone donor table lives in
`platform/xbox360/cpp-compat/fast3d/unit_color.h` with its source hash.

No texture addressing, fog/alpha mux, framebuffer transform, LOD, primitive
depth, attribute layout or scheduler behavior changes. Length is published
before the existing Flush condition. Upstream and reference trees stay read-only.
The Smash/BattleShip/Fast3D/Xbox ownership boundaries remain intact.

Eight Fast3D tests pass, including 65,536 original/projected actual packing
loop comparisons and every possible byte quotient. Full XDK/link/logger/RDP
checks pass. Actual PPC uses the exact BE table and one final buffer-length
store; 16 static integer-to-float conversions and 16 static divides disappear
from GfxSpTri1. Evidence and limits are in
`scratch/evidence/vertex-packing/ANALYSIS.md`. Static instruction removal is
not a console performance measurement.

Rebuild: `python -B tools/prepare_fast3d_xdk.py`,
`platform/xbox360/build.ps1`, `platform/xbox360/package.ps1 -ProfileDisabled`.
New package: `dist/Smash360/Smash360.xex`, SHA256
`3A52479475AFCE1792798CA947C5731B245079FF7BBCA2197CCCAEE9C25086E5`.
Profiling remains off for comparison with the last console run; 1x MSAA
default and assets remain unchanged. No runtime launch or computer control
was used. Physical-console improvement and visual correctness remain unverified.

## Unresolved 18-Yoshi stall: inner-path evidence (2026-09-20)

The new console launch after vertex packing still reaches only 41.21 FPS in
its slowest window, with 21.212 ms render and 3.029 ms logic. The attached log
contains the entire prior capture plus 13 new windows; analysis uses the last
launch only. Evidence: `scratch/evidence/hardware-vertex-packing-20260920`.
The previous change is not a solution to the reported slowdown.

Source reconstruction confirms 18 deliberately low-detail, frozen-pose Yoshis,
one stage camera, and one fighter draw per visible Yoshi. The separate player
card adds one fighter. No native duplication was found. Legitimate joint,
material, matrix and light work scales with their count. The broad log does
not establish which remaining inner operation dominates that workload.

A diagnostic projection now samples approximately 1/64 production triangles,
splitting their actual work into nine phases without changing game behavior.
It is independent of the full profiler, which stays off. Reporting includes
sample sizes/raw ticks and labels extrapolated times as estimates. Tests cover
selection, disabled mode, early returns, phase accounting and counter rollover;
the existing eight Fast3D tests and XDK/link/logger/RDP guards pass.

Reproduce with prepare_fast3d_xdk.py, build.ps1, then
`platform/xbox360/package.ps1 -ProfileDisabled -TriangleTrace`.
Diagnostic XEX SHA256:
`4434A12BDF950F65815726E5084252CFEABF55D0C6C3947EEFE65D98412644DA`.
Copy both XEX and smash360.env. This is explicitly an evidence build, not a
performance fix. The unresolved blocker is a physical-console sample of the
remaining inner cost. No computer control or emulator launch was used. 18
Yoshis, real gameplay, scheduler, assets and ownership boundaries remain intact.

## Compile full-profiler overhead out of normal builds (2026-09-21)

The next physical-console sample still measures 41.21 FPS for the populated
Yoshi intro: logic 3.115 ms, render 21.126 ms, present 0.023 ms. Its 4,185 triangle
requests/frame estimate only 6.280 ms inside triangle phases, leaving roughly
14.846 ms outside those phases. Sampling has overhead and variance; this is
not an exact CPU/GPU partition. Capture and analysis:
`scratch/evidence/hardware-triangle-trace-20260921`.

Runtime-disabled profiling still compiled scope initialization, branches and
stack traffic into hot command handlers. Default native projects now define
`SMASH360_ENABLE_FULL_PROFILING=0`, erasing full-profiler scopes and counters.
`platform/xbox360/build.ps1 -FullProfiling` explicitly restores them in both
native projects. The runtime env alone cannot enable absent scopes. Build
options are recorded against the XEX SHA256; packaging rejects mismatched
receipts and rejects `-ProfileDetail` unless the build includes full scopes.
The lightweight triangle sampler remains independent and enabled in this package.

The production-header XDK probe passes: nested disabled scopes and counters
reduce to an add and return, while full mode contains real time-base reads.
The existing accounting/sampling test passes. Full XDK build, native scheduler
ownership, logger control-flow and RDP initialization guards pass. In the actual
linked PPC, gfx_step shrinks from 989 to 371 static instructions, Run from 374
to 329, and GfxSpVertex from 833 to 722. Their full-profiler time-base reads
disappear. These counts include formerly inactive branches; they are not
dynamic instruction savings or measured console speedups. Evidence:
`scratch/evidence/full-profiler-removal`.

Reproduce with `platform/xbox360/build.ps1`, then
`platform/xbox360/package.ps1 -ProfileDisabled -TriangleTrace`.
Packaged XEX: `dist/Smash360/Smash360.xex`, SHA256
`AAB424FFC3B62049E05067E075F50DA3140F047239B2CE52B4567F8940000EC8`.
Copy the matching `smash360.env` with it. Startup should report
`PERF full_scopes_compiled=0` and triangle sampling enabled. Hold the fully
populated Yoshi intro for about 20 seconds for comparison.

The Yoshi slowdown is not declared fixed. Console measurement of this change
is pending. No computer control or emulator launch was used. Game commands,
fighter count, assets, scheduler and rendering semantics are unchanged; this
only removes optional Xbox diagnostic code from the normal build. Smash owns
game behavior, BattleShip its native adaptation, Fast3D/libultraship their
normal contracts, and Xbox the platform implementation.

## Remaining Yoshi cost: command walk and vertex lighting (2026-09-21)

The user reports roughly 45 FPS after compiling out full profiling. The new
capture verifies that mode. Its heaviest five-second window averages 47.52 FPS,
17.131 ms render and 3.289 ms logic, but mixes lighter frames: 3,797 triangle
requests/frame versus 4,185 when fully populated. Triangle phases estimate
5.852 ms, leaving approximately 11.279 ms outside them. This still does not
establish the dominant remaining operation. Input evidence:
`scratch/evidence/hardware-profiler-removed-20260921`.

The owned Xbox projections now address three separate repeated costs:

- Read the command-stack top for debugging only when debugging is active.
  XDK's deque iterator construction was otherwise paid for every command.
  The original deque, references, pushes, returns and branches remain intact.
- Query the text logger's existing enabled state before entering its buffer
  routine. Keep the callback and all BattleShip RCP cost-model calculations.
- Import SoH's exact signed/unsigned byte-to-float tables into lighting operands,
  avoiding GPR/FPR store-load conversions. Preserve BattleShip integer rounding,
  positional lights, texture generation, fog, clip bits and all light state.

The callback passes 131,072 original/projected cases with identical cost totals.
Lighting passes 32,768 real vertex cases and every byte value; XDK probes and
linked PPC confirm direct table loads. GfxSpVertex static fcfid count drops
31 to 19; CalculateNormalDir drops 3 to 0. All 11 Fast3D tests and both scope/
sampler tests pass, as do native XDK/link/scheduler/logger/RDP guards.
These establish preserved contracts and emitted code, not console speedup.

An optional command sampler now measures real Run setup, walk and finish totals,
then samples one command in 128 for fetch, bounds, callback and opcode-handler
attribution. It complements the triangle sampler without reinstating the full
profiler. Its selection/checking overhead remains inside measured walk time;
sampled estimates include observer overhead. Handler timing includes nested
triangle/backend work and must not be summed with triangle estimates.
Evidence, disassembly and rejected alternatives:
`scratch/evidence/command-lighting`; usage: `platform/xbox360/runtime/PROFILING.md`.

Reproduce: `python -B tools/prepare_fast3d_xdk.py`,
`python -B tools/prepare_port_xdk.py --prepare-only`,
`platform/xbox360/build.ps1`, then
`platform/xbox360/package.ps1 -ProfileDisabled -TriangleTrace -CommandTrace`.
XEX: `dist/Smash360/Smash360.xex`, SHA256
`A21640369D0514D72E9EC00718C06E54560B6333A9A1C1C0EDF027D4ED185792`.
Copy the matching env file. A roughly 20-second hold after all Yoshis appear
will provide pure windows and identify the remaining cost. Console performance
of these changes is pending; the slowdown is not declared resolved.

No computer control or emulator launch was used. No reference or upstream tree
was edited. Smash behavior, BattleShip adaptation, Fast3D/libultraship contracts
and Xbox platform ownership remain separated; no fighter or command is omitted.

## Command-fetch and bounds costs identified (2026-09-21)

The first CMD_TRACE capture places 16.176 ms in command execution out of
16.973 ms render. Setup/final composition are .255/.034 ms. Fetch, bounds and
callback estimates are 1.394/2.476/1.353 ms; TRI2 and vertex handlers estimate
4.935/2.546 ms inclusive. These sampled estimates contain observer overhead
and overlap triangle work. The heavy window averages 48.34 FPS but mixes
lighter frames: 13,391 commands and 3,898 triangle requests/frame. Input and
interpretation limits: `scratch/evidence/hardware-command-lighting-20260921`.

Three repeated costs are removed in owned Xbox adaptations:

- Cache the address of the current slot in the existing std::stack/deque.
  Refresh on mutation; retain BattleShip's call, branch, return and parent
  references. The internal C++ type gains a pointer and padding; all consumers
  rebuild together. Game/serialized layouts are unaffected.
- Replace Xbox acquire-load CAS sequences with aligned native loads followed
  by lwsync and explicit compiler barriers, following local XDK documentation.
  Keep registry generation checks per command and all writer synchronization.
- Read the thread-local bounds-hit cache directly during its predicate,
  avoiding an XDK-generated stack copy and dependent reloads.

The command sampler's unsampled specialization now erases phase checks from
the same authoritative command body; its original warning counter is shared.
Full-profiler scopes remain compiled out. Bounds classification, UNKNOWN cache,
locked misses, scheduler, callback timing model, rendering and all fighters
remain intact. SoH's direct command cursor was inspected but its different
recursive walker was not transplanted over BattleShip's execution model.

13 Fast3D tests pass, including 100,000 actual stack-operation comparisons,
deep nesting and retained references. Atomic and bounds tests pass, including
ordering/emission checks and host publication/invalidation tests. Both sampler
tests and compile-mode test pass. Full XDK native/link/scheduler/logger/RDP
guards pass. Linked PPC verifies direct slot loads, ld/lwsync acquire reads,
no hit-cache temporary copy and no timer reads in the unsampled command body.
Evidence: `scratch/evidence/command-cursor-acquire`.

Reproduce: prepare_fast3d_xdk.py, prepare_port_xdk.py --prepare-only, build.ps1,
then package.ps1 -ProfileDisabled -TriangleTrace -CommandTrace (same paths as
the preceding entry). XEX: `dist/Smash360/Smash360.xex`, SHA256
`430EB4140B700D54DD25CD9E39A48E02133A6337E9CD0B583C877DE3AFE76EEB`.
Copy the matching env file and return another console capture. These fixes
target measured command-volume costs, but console speed is still unverified.
No computer control was used. The architectural ownership boundaries remain
intact; the remaining slowdown is not declared fully resolved.

## Material reuse and remaining command overhead (2026-09-21)

The user reports approximately 50 FPS after the command-cursor/acquire build.
The submitted log is preserved in
`scratch/evidence/hardware-command-cursor-acquire-20260921`. Its busiest
5-second window averages 52.58 FPS: logic 3.596 ms, render 11.786 ms,
present 3.636 ms, 10,350.64 commands and 2,995.16 triangle requests/frame.
These are mixed-scene windows, not an isolated 18-Yoshi hold. Do not interpret
the render decrease relative to the earlier capture as a measured speedup of
that size. Command walk is 11.128 ms; sampled vertex/TRI2 handler contributions
are 1.995/3.815 ms. Texture setup and vertex packing remain significant.

The next package makes three narrow changes in the owned Xbox projection:

- Adapt SoH's `SoHTextureGeometry` and `SoHDrawOptionsCache` value-cache pattern.
  Cache only pure texture extent/clamp and blend-option calculations, with
  all inputs checked on each request. The cold arithmetic is extracted from
  pinned BattleShip, with source hashes requiring re-audit if it changes.
  Preserve loaded stride selection, RGBA32, floating tile extents, masks,
  mip base selection, dual-cycle alpha and blend-color semantics. Shader
  stack/masked/blended option bits are still applied afterward. Cache storage
  is thread-local POD and retains no resource pointers.
- Retain the same integer-to-float texture dimensions and bounds in that
  cache for UV packing. This follows SoH's float texture-axis representation;
  BattleShip's divisions, operation order and framebuffer UV transform stay
  intact. No reciprocal approximation is introduced.
- Inline the existing valid interpreter-owner borrow. Move the original
  temporary weak-lock expression into one cold helper for both invalidated
  and outside-walk calls. Lifetime, nested scopes and setter invalidation
  remain unchanged; no ownership or reference counting is removed.

Donor sources inspected read-only: SoH360
`platform/xbox360/fast3d_texture_math.h` and
`upstream/libultraship/libultraship/Lib/Fast3D/gfx_pc.cpp`.
Implementation: `tools/material_math_projection.py`,
`tools/dispatch_owner_projection.py`, and
`platform/xbox360/cpp-compat/fast3d/dispatch_owner.h`.
Texture imports, sampler reconciliation, shader changes, flushes, framebuffers,
bounds checks, RCP accounting and all fighters still use the real existing path.

Validation: 15 Fast3D tests and both sampler/scope tests pass. This includes
5,111,808 original/projected material cases with independently primed key
mutations and repeated hits, and 65,536 bitwise vertex-stream comparisons
including large unsigned dimensions. Native XDK/link/scheduler/logger/RDP
guards pass. Linked GfxSpTri1 has 12 static fcfid sites instead of 18, and
its integer dimension division is confined to the cache rebuild. Real TRI2
and MoveWord handlers now load the pinned owner directly on the valid path.
These are emitted-code and behavior checks, not a console speed measurement.
Evidence and old/new disassembly: `scratch/evidence/material-cache`.

Reproduce: `python -B tools/prepare_fast3d_xdk.py`,
`platform/xbox360/build.ps1`, then
`platform/xbox360/package.ps1 -ProfileDisabled -TriangleTrace -CommandTrace`.
XEX: `dist/Smash360/Smash360.xex`, SHA256
`A490DC6AC539DA4B1572994F2C36B7ABE6B47B0D3CA7DC841107DFE792E73072`.
Copy the matching `smash360.env`; samplers stay enabled and full profiler
scopes remain compiled out. A 20-second fully populated Yoshi hold will give
several comparable complete windows. Visual and performance validation of
this package on physical hardware is pending; the slowdown remains open.

Further lighting optimization was audited but not blindly imported: SoH's
64-bit FPR truncation is not equivalent to BattleShip's 32-bit integer casts
for exceptional values. A bounded exact fast path needs separate verification.
No game or reference source was changed, no computer control was used, and
Smash/BattleShip/Fast3D/Xbox ownership boundaries remain intact.

## Near-complete Yoshi window: cold work on hot paths (2026-09-21)

The material-cache package capture now contains 4,182.68 triangle requests
and 14,351.17 commands/frame, close to the fully populated 4,185-triangle
scene. It records 260 frames / 5.011 seconds = 51.89 FPS, with logic 3.167 ms,
render 15.598 ms and presentation .509 ms. Command walk is 14.906 ms.
Sampled bounds/callback/vertex/TRI2 contributions are 2.158/1.264/2.709/5.242 ms.
These estimates include observer overhead; triangle timings are nested in
handler timings and cannot be summed with them. Input capture is preserved
in `scratch/evidence/hardware-material-cache-20260921`.

The next package addresses four verified sources of repeated work:

- Bounds cache hits previously entered a 192-byte scan frame and saved nine
  nonvolatile registers. Move the unchanged locked scan into a noinline cold
  helper. Every call still acquires/checks registry generation; classification,
  overlap precedence, unknown gaps and mutation invalidation remain intact.
  Linked PPC now has no stack allocation, stores or calls in the cache-hit
  function, and tail-branches to the scan on misses.
- About 48% of sampled triangles reject before emission, yet entered the
  full 784-byte frame. Adapt SoH's `gfx_sp_tri1` / `gfx_sp_tri1_emit` boundary.
  The authoritative culling prefix and entire emission suffix stay intact;
  the latter moves to `XboxEmitTriangle`. Original timing/profiling scopes
  remain alive in the caller. Linked culling frame is 256 bytes; full emission
  frame is 768 bytes and is entered only for triangles accepted by the
  original culling rules. This adds an internal method, not another renderer.
- Skip the reloc-file scan for seg-E stride correction only when the result
  provably cannot change the resolved pointer (or the offset was already
  ineligible for correction). Keep genuine corrections, token precedence,
  the subsequent packed fallback and bounds checks. This is especially useful
  when Xenon's native and packed Gfx strides match.
- Adapt `SoH_TruncateLightChannel` from SoH's `fast3d_float.h` for bounded
  lighting accumulation. With at most 33 lights and each positive intensity
  below 1024, RGB remains below 2^23 and every truncated integer is exactly
  representable as float. Preserve each separate multiply/add/truncate. On
  the first out-of-bound positive intensity, permanently resume BattleShip's
  original 32-bit integer path for that vertex. Positional intensity math,
  texgen, fog and clipping remain unchanged. Exceptional values do not use
  an assumed-equivalent 64-bit cast.

Changes are in owned `bounds_cache_projection.py`, `command_work_projection.py`,
`triangle_split_projection.py`, `vertex_lighting_projection.py`, and
`platform/xbox360/cpp-compat/fast3d/vertex_lighting.h`. SoH was inspected
read-only; upstream BattleShip remains unchanged.

Validation: 18 Fast3D tests, both scope/sampler tests, and the original/projected
ILP32 bounds differential/concurrent invalidation test pass. Added coverage:
524,288 stride cases, 131,072 cull-to-emit/control/scope cases, and 12,800
unsaturated lighting boundary/exception/fallback cases alongside the existing
32,768 full vertex comparisons. XDK probes confirm three separate RGB
multiply/add/fctidz/fcfid sequences without integer spills; the original
fctiwz fallback remains. Native build/link/scheduler/logger/RDP guards pass.
`tests/graphics/check_hot_frames.py` checks the linked PPC layout. Evidence:
`scratch/evidence/bounds-cull-lighting` and `scratch/fast3d-xdk/lighting-tests`.

Reproduce: `python -B tools/prepare_fast3d_xdk.py`,
`python -B tools/prepare_port_xdk.py --prepare-only`,
`platform/xbox360/build.ps1`, then
`platform/xbox360/package.ps1 -ProfileDisabled -TriangleTrace -CommandTrace`.
XEX: `dist/Smash360/Smash360.xex`, SHA256
`1157B875B9310EC20D602EAA3C5F3A59E31B08885111C69844C1ABCED76E016D`.
Use its matching `smash360.env`. Diagnostic modes remain the same for the
next comparison. Physical-console speed and visual validation are pending;
the slowdown is not declared fixed. No computer control was used. Smash game
behavior, BattleShip adaptation, Fast3D contracts and Xbox platform ownership
remain separated.

## 2026-09-21: disabled texture-import diagnostics

The next hardware capture (user: "almost") is saved in
`scratch/evidence/hardware-bounds-cull-lighting-20260921`. Later gameplay
repeatedly reaches nominal 60 FPS; the heavy transition spans mixed windows
at 53.38 and 55.16 FPS. Neither isolates the full approximately 4183-triangle
Yoshi population, so its exact rate remains unproven. See that directory's
`ANALYSIS.md` for timings and comparison limitations.

Two connected hot-path costs were verified and removed without changing
rendering or batching:

- `tools/import_diag_projection.py` moves BattleShip's exact import-log
  acceptance predicate before argument preparation at all three import,
  cache-hit and cache-miss sites. Armed credit consumption still precedes
  filtering and quota checks, and armed captures still work with the
  environment diagnostic switch off. Each normal import visits two stages.
  The linked production executable skips 62 payload-preparation instructions,
  including four float-to-integer conversions, at each disabled stage.
- `cpp-compat/fast3d/atomic.h` uses an aligned native LONG read for its only
  load contract, the relaxed diagnostic capture counter. XDK's
  `Source/Samples/System/ThreadSyncInterlock/Interlock.cpp` documents aligned
  native reads as atomic. Compiler barriers remain explicit; store and CAS
  remain interlocked. The old read masked interrupts and reserved/wrote the
  cache line even when zero. The zero-credit production path now bypasses
  that sequence; its isolated XDK probe is exactly `lwz; blr`. This counter
  publishes no payload. Port registry acquire/sequence fences are unchanged.

The SoH texture-binding shortcut was also audited read-only. BattleShip's
framebuffer binding and cross-slot sampler aliases prevent safely treating
the current CPU texture-cache node as proof of physical binding/sampler state.
No import Flush, SelectTexture, content hash, upload or shader operation was
removed. A future batching change needs explicit binding/sampler tracking.

Validation: all 19 Fast3D tests pass, including 1920 comparisons of actual
original/projected diagnostic calls covering enabled/disabled logging,
armed capture, filters, quotas, hit/miss stages and lazy payload evaluation.
XDK atomic probe verifies 32-bit size/alignment and native relaxed load while
retaining previous acquire/sequence ordering checks. Native build, production
link, scheduler, logger and RDP initialization guards pass. Read-only review
found no correctness issues. `tests/graphics/check_import_diag.py` verifies
the three actual linked branches bypass payload preparation/log calls and
that zero capture credits bypass reservation instructions.

Build/package commands remain as above. Current XEX:
`dist/Smash360/Smash360.xex`, SHA256
`6C16F4F0F7389A327B9956E746D87A8D8E94BCDC7647AC861CFA4FD954ABA143`.
Full profiler remains compiled out; use matching `smash360.env` with command
and triangle sampling enabled for comparison. Frozen executable, map, XEX,
receipts and before/after disassembly: `scratch/evidence/import-diagnostic`.
Physical-console performance and visual validation of this build are pending.
No computer control, reference-tree changes or upstream edits were made.
Smash, BattleShip, Fast3D and Xbox ownership boundaries remain intact.

## 2026-09-21: systematic current-SoH platform and Fast3D parity

The core native backend had been imported, but the earlier incremental log fixes
missed applicable SoH interpreter optimizations. This pass audits current SoH's
graphics, platform and interpreter implementations together. `SOH_PARITY.md`
records transfers, already-present implementations and semantic exclusions;
source hashes and detailed subsystem audits are in `scratch/evidence/soh-parity`.
All donors were read-only. The build consumes owned copies and deterministic
projections of the pinned BattleShip originals.

Transfers include bounded VMX position/clip and replacement-matrix conversion,
light conversion/batch reuse and exact directional texgen caching, deferred RGB
conversion reads within each fully published vertex, cached shader metadata,
cold combiner lookup, three-row triangle packing and value-keyed constants,
conservative material reconciliation, six-slot native binding certificates,
literal XDK texture slots, cached timer frequency and queued audio diagnostics.
The original material setup remains the cold path. Dirty used textures retain
their import/content checks; framebuffer, shader and external API changes
invalidate relevant certificates. No fighters, display-list work or game state
are skipped. Smash's near-plane bit, positional lighting, primitive depth,
fog/blend alpha, framebuffer UVs, texture addressing and resource lifetime remain.

SoH's lazy public vertex outputs, dirty-flag restoration shortcut, older shader
contract and OoT-specific scheduler/audio/arena operations are deliberately not
copied. They differ from BattleShip's contracts. The large shade cache belongs
to each Interpreter: putting it in TLS exceeded XDK relocation limits during
linking, so it was moved to explicit owner storage before the successful build.
Nonnearest floating-point modes and exceptional/aliased input retain scalar
fallbacks. The native FPSCR query avoids a hot CRT/kernel exception-control call.

Validation: all 36 Fast3D tests and both scope/workload tests pass. Differential
coverage includes full vertex/RSP outputs across four rounding modes, 589,824
packed triangle streams, 133,152 texture-cache/import mutation steps and 8,233
actual material-reconciliation steps (4,574 warm hits), plus 461 key mutations.
Native XDK build/link, production ownership, scheduler, logger and RDP guards
pass. Linked disassembly checks confirm the real game interpreter calls the
VMX routines, clip stores touch only the clip byte, RGB conversion stores and
finite selects are emitted, and new combiner POD fields are zero initialized.
Audio PCM/queue tests, timer tests and literal texture-slot XDK checks pass.
These receipts establish compilation and tested contracts, not hardware speed.

Reproduce from `D:\Projects\Smash360`:

```powershell
python -B tools/prepare_fast3d_xdk.py
python -B tools/prepare_graphics_xdk.py
python -B tools/prepare_gui_xdk.py
& platform/xbox360/build.ps1
python -B -m unittest discover -s tests/fast3d-xdk -p 'test_*.py'
python -B tests/graphics/test_perf_scope.py
python -B tests/graphics/check_hot_frames.py --output-dir scratch/evidence/soh-parity/linked
python -B tests/graphics/check_import_diag.py --output-dir scratch/evidence/soh-parity/linked
python -B tests/graphics/check_soh_parity.py
& platform/xbox360/package.ps1 -ProfileDisabled -TriangleTrace -CommandTrace
```

Packaged XEX: `D:\Projects\Smash360\dist\Smash360\Smash360.xex`, SHA-256
`3E553C2F6AB9CED20C1183CE6A33B5EBE13FC7FD55194FB85FD6441E28534914`.
Use the matching folder/`smash360.env`. Full profiling stays compiled out;
command and triangle sampling remain enabled. New `FRAME_WORKLOAD` bands group
frames by command count using existing frame timestamps. Frozen XEX/EXE/map,
build/test logs, receipts and source hashes are under
`scratch/evidence/soh-parity/release`; linked-code evidence is in `linked`.

The incoming hardware log is preserved under
`scratch/evidence/hardware-import-diagnostic-20260921`. Only its appended second
run was analyzed: gameplay repeatedly reaches about 60 FPS, with mixed heavy
windows at 55.96 and 54.96 FPS. It does not contain a complete isolated full-Yoshi
reporting window and does not validate this new package. No computer control or
new Xenia/console run was performed. Retest the fully populated Yoshi intro at
100% resolution / 1x MSAA, then other characters and framebuffer settings.
Performance, audio underruns and broader visual validation remain open.

Ownership remains: Smash owns game behavior, BattleShip its native adaptation,
Fast3D/libultraship their normal interfaces, and Xbox platform implementations.
