# Native warning classification

`python platform/xbox360/game-compat/audit_abi.py` recompiles six actual
generated translation units into scratch-only diagnostic objects and listings.
It records input hashes, commands and the following observations in
`scratch/game-xdk/abi-diagnostics/report.json`. It changes no game function.

| Source | Finding | Native evidence and consequence |
| --- | --- | --- |
| n_env.c:5776,5809 | Pointer to u64 back to pointer | Both optimized functions load `next` with `lwz r9,0(r11)` and move it into the loop pointer. No sign-extension instruction remains. The final pointer retains all32 bits, including bit31. |
| taskman.c:583,611 | Cache round-up casts pointer to u64 | `extsw`, add15, unsigned divide/multiply16, then `slwi` and `stw` into 32-bit task pointer fields. The final low32 equals `(p+15)&0xfffffff0` for either sign or zero extension; this also holds across 0x7fffffff and 0xffffffff wrap. No high address bits reach an RSP field. |
| objdisplay.c:1969,2024 | Pointer to diagnostic u64 | `extsw r5` affects only `gcLogSuspiciousDLPointer`. Its unsigned threshold returns for every raw>=0x10000000, so high-bit native addresses return under either extension. For low token-shaped values, both representations are identical. Subsequent GBI emission independently loads the original pointer and stores its low32 with `stw` at command offset4. |
| lbparticle.c:1749 | 32-bit shift promoted to64 | Actual bank array has16 entries; the loop compares j<16. Mask rotates from1 through0x8000; `extsw` therefore never sees bit31. No camera-mask bit needed by this loop is lost. |
| lbcommon.c:2266 | Uninitialized f[2][2] in upstream `// FAKE` expression | Source-level undefined read feeds a temp and empty conditional. Pinned /O2 eliminates the read entirely; no `lfs f$+28h` occurs. The routine stores f[2][2] from dist.z before syMatrixF2LFixedW, and initializes all12 elements that that converter reads. Its fourth column is deliberately supplied by the converter, not read from f. This is not a claim that the source is defined under other optimizers. |
| mnvsresults.c:3140 | Uninitialized first_man | Real defect: first_man is never assigned anywhere in mnVSResultsGetBestManExcept. Native code loads `first_man$(r1)` at r1-0x30 before using it to index is_human/points. Negative values can address outside the arrays; other values can skip valid ties. Auto-handicap calls it for best-handicap1/worst8 and best2/worst9 with at least two human players. There is no calling convention initialization of this local. No replacement starting value has been invented. |

The pointer warnings above require no blanket casts. The first_man defect
needs a separately justified gameplay correction. Remaining warnings, including
the existing loose objdisplay callback declaration, float narrowing and old
intrinsic declarations, remain visible in `scratch/game-xdk/diagnostics.json`.
These are compiler/source observations, not console runtime results.
