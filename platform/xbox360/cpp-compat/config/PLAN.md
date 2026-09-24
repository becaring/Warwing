# Actual Config and ConsoleVariable XDK compilation plan

1. Pin each directly transformed original source/header by SHA256. Generate into scratch/config-xdk only, preserve unchanged upstream #line locations and mark inserted spans as generated.
2. Centralize AST range-for lowering derived from the existing donor/Prism implementation, including temporary lifetime and cached end. Add typed string_view contract for the actual CVar hash/equality and StringHelper consumers; unknown APIs stay absent.
3. Lower actual Config.cpp, ConsoleVariable.cpp and StringHelper.cpp syntax. Preserve the existing methods and behavior, including legacy CVar migration and serialize-before-truncate handling.
4. Stage actual Config/ConsoleVariable/Context/Window/Audio declarations. Contract pointer-only includes into forward declarations without replacing classes or fields. Any in-class initializer relocation must include its real constructor patch, even if Window implementation is outside this compile slice.
5. Reuse actual generated audio headers and centralized native filesystem. Keep logging requirements explicit until the root-owned current logging dependency provides a compiler-compatible header. No stub logger/sink/no-op error path.
6. Differentially exercise generated methods on host using parent-owned actual consumer fixtures; compile actual generated source with XDK when its include closure is available. Validate helper semantics and fail-closed generation separately. Report blocked includes explicitly if logging is still unresolved; no application/link/boot claim.
