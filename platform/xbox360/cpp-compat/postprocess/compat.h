#ifndef SMASH360_POSTPROCESS_COMPAT_H
#define SMASH360_POSTPROCESS_COMPAT_H
#include "prism/compat.h"
#include "filesystem/filesystem.h"
#include "fast3d/platform.h"
#include <cstdlib>
inline xbox_compat::filesystem::directory_iterator PrismBegin(xbox_compat::filesystem::directory_iterator& value) { return xbox_compat::filesystem::begin(value); }
inline xbox_compat::filesystem::directory_iterator PrismEnd(xbox_compat::filesystem::directory_iterator& value) { return xbox_compat::filesystem::end(value); }
namespace Smash360PostProcess {
inline float ParseParameterFloat(const char* input, char** end) {
#ifdef _XBOX
    int error = 0;
    return _Stofx(input, end, 0, &error);
#else
    return std::strtof(input, end);
#endif
}
inline long RoundPixels(float pixels) { return static_cast<long>(Smash360Fast3D::RoundViewport(pixels)); }
}
#endif
