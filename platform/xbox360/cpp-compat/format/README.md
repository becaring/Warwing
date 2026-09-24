# Formatting compiler dependency

The XDK formatter is official fmt **4.1.0**, commit
`135ab5cf71ed731fc9fa0653051e7d4884a3652f`, unmodified under
`upstream/dependencies/fmt-xdk`. This is an explicit temporary dependency
deviation from spdlog 1.16's bundled fmt 12.0.0, not a claim that the releases
are interchangeable. The official legacy fixed-arity API supports the XDK
compiler without a replacement formatting parser. The authoritative current
spdlog logger, queue, sink and registry behavior is adapted separately.

Include this directory's `format.h` and add the fmt-xdk checkout root to include
paths. PPC leading-zero intrinsics replace the library's desktop x86 intrinsic
selection; disabling Windows-error wrappers avoids desktop windows.h. No source
file in the dependency checkout is modified. `fmt::ptr` is the modern explicit
pointer cast; values still go through the original formatter.

The legacy API provides up to 15 formatting arguments. Unknown custom formatters
must fail compilation, not stringify arbitrary objects. Larger reached arity
requires an explicit source-mapped extension before it may compile.

## Temporary differences requiring integration audit

Default floating formatting and some floating exponent/error-message spellings
can differ from fmt 12. They may affect diagnostic messages. This limitation
must not be accepted for game state, archive names, resource identifiers, shader
generation, configuration serialization, or any value reparsed by production
code. Those systems retain their existing paths; JSON numeric serialization
uses the separately validated current JSON algorithm. A build integration audit
must classify every reached fmt call before adopting this dependency. Modern
runtime format-string wrapper and custom-format APIs are not implicitly supplied.

Replace this dependency with a faithful current-fmt compiler lowering when
practical. Keep the call boundary centralized so that no game-source changes
are needed for that replacement. The initial native compiler probe succeeds;
consumer differential checks and whole-application use remain separate evidence.

`tools/audit_format_consumers.py` now inventories 328 AST calls across the
selected production sources and public headers, including 68 direct fmt calls.
The non-diagnostic consumers construct GUI labels/IDs with strings and integer
indices, plus debugger breakpoint IDs from pointers. The inventory retains
actual expressions and source hashes. Unknown direct APIs/consumer files fail
closed. Existing integer/string/pointer comparison tests cover their formatting
forms. This source audit is not proof of execution in the final application.
The logging boundary separately extends the official ArgList representation to
39 arguments and verifies it against current spdlog for the reached diagnostics.
