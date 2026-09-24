# Actual input editor on XDK

`python tools/prepare_input_editor_xdk.py --compile` projects the pinned current
InputEditorWindow.h and entire 1477-line InputEditorWindow.cpp, with SHA256 input
locks and original/generated line mappings. Upstream/reference files remain
read-only. The reusable sparse overlay is
`scratch/input-editor-xdk/overlay/libultraship/{include,src}`. Compose it with the
current controller header projection, root Gui/Context projection, graphics
GuiWindow/GuiTexture headers and real ImGui. The generated manifest records every
selected support header hash; the compile report records the exact XDK command.

Language changes are explicit constructor forwarding, typed set insertion,
two-element stick/four-element direction arrays, pair-binding/range lowering,
typed sort lambda, ImVec4 constructor spelling and named Color_RGB8 aggregate.
Mapping IDs, config keys, duplicate device-name disambiguation, port toggles,
mapping edits/removal/defaults, input blocking, deadzone/sensitivity/notch controls,
four port tabs, rumble tests, and saved LED/gyro mapping editing remain the current
implementation. Range lowering caches the end and preserves temporary lifetime
and value/reference binding. No replacement ControlDeck or editor is introduced.

Xbox platform changes are bounded:

- Guard the Raphnet manager include and native-port explanatory/banner/binding
  block with `!defined(_XBOX)`. The original enum/color metadata remains, including
  serialized Raphnet device identity. Controller transport guards are owned by
  the controller projection; no USB/mock transport is introduced.
- Gamepad-only popup placement uses ImGui's normal popup placement. Xbox does not
  call GetMousePos/SetNextWindowPos with an absent mouse position. The desktop
  offset behavior remains under its platform guard.
- Gyro and programmable LED sections explain that Xbox 360 gamepads lack those
  capabilities, while keeping existing saved-mapping editing/removal available.
  The native physical API reports those operations unsupported. Keyboard/mouse
  defaults remain editable serialized configuration; this does not add keyboard
  or mouse input hardware. Gamepad navigation input is the native ImGui backend's
  separate responsibility.

`python tests/input-editor-xdk/run.py` executes exact extracted original and
projected InitElement/UpdateBitmaskToMappingIds/UpdateStickDirectionToMappingIds
methods against a test-only object graph. It checks initialization, all four
ports, preserved insertion ordering for newly added IDs, no duplicates, and
left/right stick/direction routing. It does not substitute a production class.
The same test audits all 81 StringHelper::Sprintf format strings unchanged: no
floating conversions and no fmt:: calls occur in this editor. Widget identifiers
therefore do not depend on the temporary fmt4 floating-format deviation. ImGui
slider/display printf formatting remains its real implementation.

The complete projected editor compiles to an actual XDK object with real
controller, Gui, and ImGui headers. Existing narrowing warnings for frame timers
and the SDK decorated-name-length warning remain visible in compile.log.
Host method comparisons and XDK compilation are not runtime UI interaction,
controller hardware verification, final linkage, or Xbox/Xenia execution.
