# Actual GUI widget XDK projection

`python tools/prepare_gui_widgets_xdk.py --compile` hash-checks and source-maps
the twelve complete pinned widget/resource sources. Output is
`scratch/gui-widgets-xdk/generated/{include,src}`; `compile-audit.json` records
each XDK command and result. These are the actual widgets, including the console
and graphics debugger. The generator consumes the real root-owned Gui,
Fast3dWindow, ImGui, resource, configuration, logging and Fast3D projections.
STB is the pinned actual upstream dependency.

Inherited constructors become explicit forwarding overloads. Member defaults,
including the console's three const vectors, finish initialization before the
constructor body. Delegating constructors copy the exact primary initializer
and body with the actual argument substitutions. Scoped enum values, range
binding/copy behavior, cached range ends and seven console command records remain
intact. XDK's lambda-default-argument compiler failure is avoided by explicitly
passing the original default at every corresponding call.

`GuiWindow()` now explicitly sets its flag to zero, preserving the defined
value-initialized result; plain default initialization previously left that flag
indeterminate. The debugger uses ImGui's actual clipboard API, like the console,
so the native context clipboard remains usable without SDL. Stats identifies
the Xbox platform. Console formatting uses the real C99-compatible snprintf
adapter, including the sizing pass, rather than the XDK truncating CRT variant.

`python tests/gui-widgets-xdk/run_host.py` compares the actual original and
projected GuiElement lifecycle and Console methods: initialization idempotence,
visibility, update/draw callbacks, argument defaults/usage, duplicate command
registration, real stored callback invocation and command-map behavior.
Console::Run requires an application Context and is excluded from that host
closure; its complete production source is XDK compiled. Logging is explicitly
compiled out only for this pure-method host test, using real spdlog's active-level
selection. No production dependency class or service is mocked.

`python tests/gui-widgets-xdk/test_prepare.py` verifies every actual command
record, const-vector element and debugger lambda call against pinned source.
The complete header probe instantiates the production inherited constructors.
Application linking, interactive drawing, target execution, and the optional
upstream GFX_DEBUG_DISASSEMBLER/libgfxd configuration remain separate work.
