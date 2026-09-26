# Development

## Make changes at the owner

Edit maintained adapters or projector code, then regenerate. Generated C/C++,
projects, objects, archives, logs, and executables are outputs. Keep BattleShip
behavior in the consumer integration and generic Xbox services in Shipyard.
Preserve locks, manifests, legal notices, provenance, and upstream sources.

Trace a change from the selected input through its adapter/projector to emitted
code and the production project manifest. Missing semantic references in a
partial index do not prove that a function has no callers. Preserve useful
`#line` mappings and fail generation when an expected source anchor changes.

## Verify the affected contract

Use the existing focused tests under `tests/`. Relevant suites include
`fast3d-xdk`, `port-xdk`, `graphics`, `audio`, `endian`, `async-compat`, and the
configuration/resource compatibility suites. Their fixtures exercise original
and generated implementations, ABI/layout, exceptions, mutation, cache
invalidation, and ownership. Follow each suite's prerequisites; there is no
single portable command that replaces all host and XDK checks.

For bounds work, run:

```powershell
python -B tests/port-xdk/test_bounds_cache.py
```

For a stable change set, run the selected Xbox integration build described in
[building](XBOX360_BUILDING.md). Preserve the previous XEX and its receipt before
replacing a candidate. Associate runtime results with the exact executable,
source revision, options, and dependency pins. Host differentials, PPC code
inspection, Xenia execution, and physical-console tests establish different
kinds of evidence; report their limits separately.

## Performance work

First establish the actual call path and frequency. Prefer eliminating proved
redundant work over adding caches. A cache requires a complete key, lifetime,
invalidation, owner, memory bound, and observation contract. Preserve arithmetic
order, rounding, unsigned wrap, aliasing, publication, and synchronization.

The bounds fixture provides one structural example: first-range positive misses
perform zero gap exclusions instead of two; first-range walked-past results
across three ranges perform zero instead of six. A true UNKNOWN scan still
performs all six exclusions. Those counts do not establish a console FPS gain.

Normal builds omit the full profiler. For controlled measurements, use the
[profiling guide](../platform/xbox360/runtime/PROFILING.md), keep the scene and
options comparable, and record warm/cold shader state. Never sum inclusive
nested timings, infer GPU duration from a blocking CPU API interval, or subtract
an observer estimate as if it captured every profiling effect.

Maintain a short description of the changed contract, deterministic evidence,
and remaining runtime uncertainty with each change. Separate readability-only
changes from semantic and performance changes. Avoid preserving chronological
work logs as the project's main technical documentation.
