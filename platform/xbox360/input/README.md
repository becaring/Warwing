# Native physical input boundary

Run `python tools/prepare_input_xdk.py`. Prepend the generated
`scratch/input-xdk/source/libultraship/include`, Shipyard's `sources` directory,
and this directory to includes, and prefer the generated source files over their
matching pinned originals. Compile Shipyard's `sources/input/physical.cpp` and
`sources/input/xinput.cpp` directly with `window_input.cpp`. Do not add a global
SDL include shim. `smash360_input_sdl.h` is an explicit, controller-only source
bridge to Shipyard input. Its logical button/axis values match the
existing configuration fields and the proven SoH360 physical translation.

Original ControlDeck, controller, button/stick mappings, factories, config IDs,
blocking, simulated input delay, sensitivity, circular deadzone, octagonal
limit, and notch snapping remain in the current application. The bridge exposes
raw sticks, inverted Y with -32768 saturation, and triggers scaled to 0..32767.
Applying donor deadzones here would apply deadzones twice. Guide, paddles, touch
pad, gyro, and programmable RGB LED have no supported XInput inputs/capabilities.
Unsupported effect/sensor operations return failure; no success data is made up.

Four physical slots are polled into a coherent snapshot per pump. Device indices
are compact connected-device indices; instance IDs change after reconnect, as
they do for SDL devices. Bounded handles are owned by the bridge for the process
lifetime. The existing manager refreshes on native topology changes, preserving
its ignored-instance routing and new-device port assignment algorithm. This runs
from actual LUS WriteToOSContPad, so it does not depend on showing the GUI's device
event handler. ImGui's platform NewFrame samples all four slots before selecting
the first connected physical slot from the cached raw state. The GUI device
handler consumes that presentation sample once, then refreshes topology. If no
presentation sample exists, or an ordinary pump intervened, the handler polls
afresh. Window events and game reads always poll independently; no clock-based
cache is used. No SDL event queue is
implemented. Slot GUIDs are stable; USB vendor ID is unknown (zero), not invented.
Call the bridge from the application's input/window thread; no concurrent polling
contract is provided.

Rumble preserves the current mapping's independently configured low/high motor
intensities. Its duration-zero calls mean sustained until the mapping explicitly
stops. This is a deliberate current-application contract, not a claim of general
SDL duration semantics. Nonzero durations expire during pumping, including tick
wraparound. Call `ShipyardInput_StopPhysicalRumble` before platform shutdown, in addition
to the actual ControlDeck's StopAllRumble, so removed mappings cannot leave a motor
active. No synthetic presses, scene advancement, or tap injection is used.

Graphics service implementations poll real gamepads and report absent keyboard
and mouse: no callback events, motion, wheel, buttons, or captured pointer. Pointer
setters have no device to affect; KeyName returns Unknown. Window running state is
left with its owner. ImGui gamepad navigation is not implemented by this physical
bridge; integrating its real backend inputs is separate from gameplay mapping.

## Explicit integration dependencies

The sparse overlay is composed before C++ language lowering; it does not make
modern current classes directly XDK-compatible. The main class lowering pipeline
must compile their genuine transformed sources with these input overlays first.
Eight source/header originals are locked by SHA256 and output hashes are recorded.

Raw Raphnet HID is unsupported on this platform. No HID or mock-keyboard transport
is supplied here. The integration must exclude `ControlDeck::PreInitRaphnet` and
Raphnet bind/poll/rumble paths at the platform boundary, or provide an explicit
unsupported transport with the real manager interface. Merely setting its CVAR
off leaves linker references in PreInit/Shutdown/Init and LUS::Controller, and
InputEditor may also reference the manager. Do not link MockRaphnetTransport as an
XInput substitute: that bypasses the current mapping pipeline. The original
Raphnet source is unmodified and this dependency remains visible.

Keep current libultraship/libultra/os.cpp `osContGetReadData` intact: LUS's extended
OSContPad is larger than the game's six-byte structure. Its local LUS buffer and
field-by-field copy are required. Neither the native adapter nor this overlay
writes N64 pad memory directly.

## Verification and limits

`python tests/input/run_tests.py` compiles/runs the real current device manager
with test-only physical reads and logger sink. It exercises four slots, manual
routing, stable routing across ordinary polls, reconnect assignment, SDL numeric
buttons, raw axes/trigger/Y conventions, no double deadzone, sustained/timed motor
effects, timer wrap, and unsupported capabilities. Exact extracted current button
and axis methods execute with a test Context seam to check remapping and blocking.
The exact current osContGetReadData method is tested with guarded six-byte records.
Native production files and the actual local pad-layout declaration also compile
with XDK; the latter asserts size 6 and error offset 4.

These are host behavioral tests and PowerPC compile evidence, not Xbox/Xenia
execution, complete fullclass linkage, or physical controller/rumble validation.
