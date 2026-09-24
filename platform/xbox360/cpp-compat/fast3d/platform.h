#ifndef SMASH360_FAST3D_PLATFORM_H
#define SMASH360_FAST3D_PLATFORM_H
#include <cmath>
#include <stdint.h>
#include <float.h>
#include <stdexcept>
#include "../../environment.h"
#include "crt/snprintf.h"
#ifdef _XBOX
#include <ppcintrinsics.h>
#else
#include <emmintrin.h>
#endif

namespace Smash360Fast3D {
// Xbox SDK 21256.3, dev_linker_images.htm: XEX 64-KB pages load at
// 0x82000000..0x8BFFFFFF; 4-KB pages at 0x92000000..0x9BFFFFFF. Even
// low preferred image bases are remapped there. The interpreter invokes
// this exception only for <=0x0FFFFFFF, where no loaded XEX can reside.
// This deliberately is NOT a general module-address query.
inline bool LowAddressInLoadedModule(const void* pointer) {
    if (reinterpret_cast<uintptr_t>(pointer) > 0x0FFFFFFFu)
        throw std::logic_error("Fast3D low-address module query outside its audited domain");
    return false;
}
// The interpreter calls round only on already-rounded binary32 viewport sizes.
// Same finite/tie-away expression as the proven SoH math_platform.cpp.
inline double RoundViewport(double value) {
    if (!_finite(value) || value == 0 || fabs(value) >= 4503599627370496.0) return value;
    return _copysign(floor(fabs(value) + 0.5), value);
}
// SDK ppcintrinsics.h explicitly specifies current-rounding-mode conversion.
// stfiwx stores the signed word unchanged; no subsequent numeric float cast.
inline int32_t RoundSignedWord(double value) {
#ifdef _XBOX
    int32_t word;
    __stfiwx(__fctiw(value), 0, &word);
    return word;
#else
    return _mm_cvtsd_si32(_mm_set_sd(value));
#endif
}
inline int32_t RoundMatrixWord(float value) { return RoundSignedWord(static_cast<double>(value)); }
template<class Map> void ReserveEntries(Map& map, size_t count) {
    map.rehash(static_cast<size_t>(ceil(static_cast<double>(count) / map.max_load_factor())));
}
}
#endif
