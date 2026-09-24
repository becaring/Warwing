# Interpreter cost investigation plan

**Goal:** Attribute the console's 8.74 ms command-step and 2.18 ms bounds costs
to actual production operations before selecting an optimization.
**Architecture:** Extend the existing SoH-derived thread-local profiler and
hash-checked source projections. Detail is optional; game decisions, ownership,
memory ordering, resource mutation and safety checks remain unchanged.
**Scope:** Only D:/Projects/Smash360 is writable. References and pinned upstream
are read-only. Real hardware is the performance authority.

- [x] Preserve the current verified XEX and profile evidence.
- [x] Add regression coverage for detail-disabled scopes preserving parents and
  for dynamic opcode section accounting, including high-bit opcodes.
- [x] Extend runtime/perf_trace.h/.cpp with optional detail scopes and 256 opcode
  slots; print only the busiest eight opcode self-times plus aggregated remainder.
- [x] In tools/profile_projections.py instrument the existing dispatch tail,
  temporary weak ownership acquisition, reloc operations and bounds-cache
  generation read, lock/scan path and hit/miss/visit counts. Compose port changes
  through tools/prepare_port_xdk.py. Retain exact expressions and lifetimes.
- [x] Run host tests, full XDK build/link/PPC guards and real Xenia execution.
  Confirm total self accounting, detail records and preserved real boot.
- [x] Review findings, document limits and produce a hardware diagnostic package.
  Implement a performance change only if the owning contract and redundant work
  are proven; do not infer console speedups from Xenia.

Selected follow-up: skip identity-only runtime texture/vertex endian repair on
BE unless explicit asset diagnostics are enabled. Container consumers audited;
extracted production functions pass BE/LE byte, overlap and deswizzle checks.
The complete XDK build/link/PPC guards pass. Inspecting linked PPC confirms the
diagnostic-off branch returns before range/word tracking. This correction has
not been launched or visually validated; the user requested no computer control.
The pre-correction detailed build was executed in Xenia. Physical-console
validation of the correction and performance comparison remain external steps.
