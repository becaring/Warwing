#pragma once
// Uses official fmt 4.1.0 as is; it is not a printf emulation.
// fmt 4.1.0 can format floats and exponents differently from fmt 12. That is acceptable in diagnostic
// messages only; game state, file names and anything parsed back keep their own formatting paths.
#ifdef _XBOX
#include <ppcintrinsics.h>
namespace xbox_compat {
inline unsigned fmt_clz32(unsigned n) { return _CountLeadingZeros(n); }
inline unsigned fmt_clz64(unsigned __int64 n) {
    const unsigned high = static_cast<unsigned>(n >> 32);
    return high ? fmt_clz32(high) : 32 + fmt_clz32(static_cast<unsigned>(n));
}
}
#define FMT_BUILTIN_CLZ(n) xbox_compat::fmt_clz32(n)
#define FMT_BUILTIN_CLZLL(n) xbox_compat::fmt_clz64(n)
#endif
#define FMT_USE_WINDOWS_H 0
#define FMT_USE_VARIADIC_TEMPLATES 0
#define FMT_HEADER_ONLY 1
#include <fmt/format.h>
namespace fmt {
// Current callers use fmt::ptr to opt into pointer formatting explicitly.
template <class T> inline const void* ptr(T* value) { return static_cast<const void*>(value); }
inline const void* ptr(const void* value) { return value; }
}
