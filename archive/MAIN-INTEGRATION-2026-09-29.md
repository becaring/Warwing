# Smash: main integration, 2026-09-29

Reviewed range: `ad7a04c0c29b71ee54fa68009346b9e74f562718..a570949450863812660644c417c760fef061d43c`.

The recorded builds and tests belong to the range endpoint above. The
documentation-only follow-up does not replace the binary build identity.

Merge the completed Smash Xbox development branch onto main while preserving
main documentation and the original development branch/worktree. Integrate the
reviewed texture-retirement/pipeline-restoration adapters, including palette
identity and reload restoration traits. Invalidate the pipeline key on framebuffer
texture registration, erase and clear; use Certify on the warm path and update
triangle pipeline and phase contract fixtures accordingly.

Retain the selected asynchronous presentation integration. Share the existing
controller-route, matrix-product and synchronous resource-cache-hit projections
through Shipyard helpers, with a differential host test confirming that resource
cache hits do not allocate a future.

Pin the canonical Shipyard base to consolidated revision
0f446c26719bb47cd0c73fd2109f0272a99cd7bd and its recomputed baseline digest.
Generation initially rejects the stale shader_lower.cpp source SHA. Verify that
the already-maintained near-plane/depth-disabled correction accounts for the
source difference, then reconcile the exact source pin while retaining ABI 3.
No shader redesign or rendering-policy change is introduced by that correction.

Validation: regenerate the selected Release projection, compile all 486 game
translation units and 252 staged application/LUS units, and link Smash360.xex.
Triangle pipeline tests pass, including 673 contract checks and 8,233 real
reconciliation/phase differential checks. The synchronous resource-cache test
and shared baseline, selection-contract, coordinate and presentation checks pass.
Native link ownership, logger control flow and RDP value-initialization checks pass.

Signed-in isolated Xenia logs show repeated frame-loop execution with full
profiling and triangle/command traces disabled. Staged binary:
Main-Integration-20260929/Smash/Smash360.xex, SHA256
4afeef2ce984da9b007735f4f5e9724d2572dbf7b6e11eb836b13bd4713c74ec.
This does not verify physical Xbox throughput. This documentation commit preserves
the existing tested sources, binary and historical commit IDs.

## Incorporated commits

```text
a570949 build: reconcile shader source pin with maintained Shipyard ABI
d15fab4 integration: make tested Smash development the main branch
37ef4b8 integration: select shared controller matrix and resource corrections
167c6f6 Select reviewed presentation scheduling and deferred depth changes
71e6892 Integrate reviewed pipeline certification and production source fixes
c4655e7 Integrate reviewed texture retirement and pipeline restoration adapters
```
