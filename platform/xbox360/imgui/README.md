# Current ImGui with the SoH360 native renderer

`tools/prepare_imgui_xdk.py` reads the pinned ImGui 1.91.9b-docking sources and
the pinned LUS configuration patch. It generates mapped compiler copies under
`scratch/imgui-xdk/source`, preserving the original checkout. Per-file locks and
the LUS patch hash are checked before transformation.

The platform base `sources/imgui/imgui_xenos.cpp` is compiled directly as the
native renderer. Device access, native-draw state, logging, and fatal handling
are narrow hooks in `platform_frame.cpp`. Font-atlas rebuilds and renderer
capability teardown live in the shared source.
`platform_frame.cpp` uses the donor timing/controller event contract with the
actual physical Xbox pad service. No second frontend or game framebuffer exists.

Compiler transformations move full enum definitions before their opaque uses,
relocate selected member defaults into constructors, lower range loops with a
cached end iterator, and replace noncapturing function-pointer callbacks with
equivalent static functions. STB multi-include headers retain their own guards;
the generator must not add an outer guard around their implementation sections.

Seven native objects compile: the five real ImGui translation units, the shared
renderer, and platform-frame implementation. `tests/imgui/run.ps1` compares
original/generated real atlas data, defaults, enum sizes and draw data for
multiple actual GUI frames. This proves the tested compiler projection, not GPU
execution. Full application/native presentation verification is still required.

First bring-up supports controller navigation. USB keyboard/text entry,
controller pointer mode, and multiple native desktop windows are not currently
implemented. These are explicit platform capabilities; the real game remains
driven through its normal ControlDeck mappings and frame path.

`tools/prepare_gui_xdk.py` adapts the existing LUS Gui platform dispatch. The
Xenos rendering API initializes that actual Gui at the same point as the
current DX11 backend. Xbox shutdown releases ImGui GPU resources before the
native rendering API destroys its device; the later base Window destructor is
idempotent against the already-destroyed ImGui context. The original game
viewport, framebuffer display and menu construction are retained.
