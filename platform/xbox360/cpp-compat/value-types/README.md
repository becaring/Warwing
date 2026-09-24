# Bounded XDK variant and optional support

Include physical Shipyard `sources/value_types` and use
`<xbox_compat/variant.h>` and `<xbox_compat/optional.h>`. These headers never
shadow `std` or replace the application's actual resource/Prism classes.
`python tools/prepare_value_types.py` verifies the checked-in Shipyard variant
against its canonical generator and removes stale local generated headers.

## Audited callers

Prism locked `1de054450e7b3c5f777d2e3dfcb228ad120c329d` uses ASTTypes with 19
alternatives, ContextTypes with 11, NodeType with 8, and the ForContext iterator
with 4. Its optional strings use empty construction, assignment, `value_or`,
`has_value`, and lvalue `value`. The LUS reader and resource cache have two typed
alternatives; the actual cache initializes from `nullptr`. MenuTypes has a
five-type CVarVariant and ten-type OptionsVariant, including inherited UI option
types, plus three value-pointer types. Prism's boolean expression results must
select `int`, not `float`, in ContextTypes.

Search of the pinned Prism/LUS/port headers and implementations found no
`std::visit`, `get_if`, `monostate`, `in_place`, `variant_size`,
`variant_alternative`, or `make_optional` use. Optional also occurs in the LUS
scripting paths for vectors, paths and callback functions; their type-specific
integrated compilation remains separate from the tested optional<string> and
shared-pointer shapes.

The SoH360 donor inventory contained no variant/optional implementation. XDK's
actual `<type_traits>`/`<utility>` provide aligned_storage, alignment_of, decay,
copy traits, moves, and forwarding, but no variant, optional, or modern noexcept
move trait. Compiler probes confirmed rvalue references, overload-resolution
`decltype`, and nullptr-to-shared_ptr. They rejected explicit conversion operators
and ref-qualified member functions. No additional library was downloaded.

## Supported contract

`variant<T0,...>` accepts 1–19 **unique** alternative types, using one inline
aligned storage region and an explicit discriminator. Defaults value-initialize
T0. No per-value heap box is used. Copy/move construction and assignment preserve
active-type destruction, moved-from source engagement, and exception transport.
A failed type-changing move leaves the destination valueless; failed same-type
assignment keeps its active type; safe-copy-before-move is used when the selected
alternative's move contract requires the strong guarantee. Copying a valueless
variant preserves that state. Assignment can recover from it.

`get<T>` supports mutable/const lvalues and rvalues; wrong/valueless access throws
`xbox_compat::bad_variant_access`. `holds_alternative<T>`, `index()`,
`valueless_by_exception()`, and `variant_npos` are provided. Type-based access to
absent types and duplicate alternatives fail at compilation.

Implicit construction/assignment uses a compiler overload set over the actual
alternatives. It supports exact types, non-narrowing arithmetic promotions,
string-literal-to-string, pointer conversions and nullptr-to-shared_ptr. Scalar
narrowing candidates are filtered before resolution. User-defined conversions
into arithmetic alternatives are deliberately rejected; a full C++17 list-
initialization/SFINAE implementation for arbitrary conversion classes is not
claimed. The audited caller conversions are covered by differential tests.

`optional<T>` has inline storage, default/nullopt empty state, value/copy/move
construction and assignment, reset, has_value, contextual boolean checks,
lvalue/const-lvalue value and dereference/arrow access, and lvalue value_or.
Bad value() access throws `xbox_compat::bad_optional_access`; dereferencing an
empty optional retains the standard precondition. A failed construction never
marks storage engaged. Moving leaves the source engaged with its moved-from T.

## Explicit boundaries

This is a bounded runtime compatibility layer, not a complete C++17 standard
library replacement. The following are **not supported/certified**:

- Duplicate alternatives, more than 19 alternatives, index-based get, visitation,
  get_if, monostate, emplace/in_place, comparisons, swap, allocator propagation,
  hash, constexpr, trivial-special-member propagation, or standard trait
  reflection of copyability/constructibility/noexcept on the wrapper itself.
  Unsupported named APIs are absent, not stubbed.
- Arbitrary implicit numeric conversion classes, arbitrary conversion-list
  narrowing rules, or converting optional<T>-to-optional<U>. Do not map new
  callers to this API without extending the audited contract and tests.
- XDK ref-qualified optional accessors. The provided accessors implement the
  reached lvalue operations; calling them on rvalues does not promise std's
  rvalue move-return behavior. XDK contextual boolean support uses the safe-bool
  idiom, so its implicit-conversion type traits differ from C++17 explicit bool.
- Throwing destructors, unusual allocator/character-traits move guarantees, or
  over-alignment beyond what the SDK aligned_storage actually supplies. A static
  alignment check rejects unsupported storage instead of silently misaligning it.
  XDK's requested 16-byte-aligned test is intentionally rejected.

`xbox_compat::is_nothrow_move<T>` is the explicit contract customization for
lowered XDK user types with known nonthrowing moves. Register it only after
checking their actual move implementation. XDK default classes are conservatively
considered potentially throwing; a nonthrowing copy alone does not prove which
constructor an rvalue selects. Shared/weak pointer moves and copies are known
nonthrowing. Default-allocator std::string/wstring/vector moves are recognized
only with iterator debugging disabled, because debug proxy allocation can throw.
Modern host builds use the actual standard construction traits. These contracts
control exception-state preservation; no exception is swallowed.

## Verification

```
python tools/prepare_value_types.py
python -m unittest discover -s tests/value-types -v
python tests/value-types/run_tests.py
python tests/value-types/run_negative.py
```

The differential test compiles/runs the same cases using std and xbox_compat,
including actual Prism AST/context/node declarations, actual UIWidgets structs
and MenuTypes aliases, and actual LUS reader/error declarations. It checks inline
alignment, default and 19th-alternative construction, conversion selection, wrong
get, switching alternatives, shared ownership, moves, valueless and throwing
construction/assignment, recovery, signed error values, and optional lifetimes.
It also verifies that a nonconvertible string literal excludes a numeric variant
constructor from an overload set containing std::string, while valid integer and
string alternative conversions remain available. The constructor's enable_if
uses the existing per-alternative conversion/nonnarrowing predicates; it does not
change alternative selection. General standard constructibility traits and
overload participation with multiple ambiguous viable alternatives remain outside
this bounded contract, as noted above.
Cases use real standard types; extracted application declarations retain their
original bodies. Primitive dependency aliases and incomplete LUS resource types
are test scaffolding, not replacement application implementations.

The same runtime cases (without the still-modern application headers) compile to
an actual XDK PowerPC object, instantiating 19 alternatives, copying/moving,
exceptions, shared ownership and optionals. Negative host comparisons confirm
both implementations reject double-to-float and pointer-to-bool narrowing and
absent-type get. An XDK negative probe confirms unsupported 16-byte storage fails
closed. Logs and generated test headers/objects are under `scratch/value-types`.

Host equality and XDK object compilation are not Xbox execution, complete Prism
integration, a linked application, or boot evidence. The graphics work owns
actual Prism source lowering/integration and shader-output differential tests.
