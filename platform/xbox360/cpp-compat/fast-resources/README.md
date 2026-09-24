# Current Fast3D resource readers

`tools/prepare_fast_resources_xdk.py` projects the five pinned binary/XML
resource factory translation units and DisplayList's destructor into
`scratch/fast-resources-xdk/generated`. The adjacent source lock records every
original hash; generated files retain source mappings.

Changes are limited to the existing variant accessor, array size expression,
range iteration, render-mode map construction, and aggregate command assignment.
Every original Gfx macro invocation initializes a local Gfx before assignment;
the arguments, order, resource lookups and command representation are retained.
The map retains the original pairs in their original order, including identical
duplicate entries. Macro calls occupy one physical line so source-mapping
directives cannot enter macro argument lists on XDK. Fast3D's existing projection
owns the three resource headers' explicit inherited-constructor forwarding.

No resource decoding, byte-swap, relocation, matrix, texture, vertex or display
list format is replaced. Both XML and binary factories remain in the production
source set. These sources have compiled in the combined Xbox project; runtime
asset interpretation and final link are still unvalidated.
