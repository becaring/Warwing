// Adapted from SoH360 platform/xbox360/math_platform.cpp FloatBits/qNaN0x10000.
// XDK C cannot statically initialize BattleShip's NAN expression. Keep the
// same externally visible float symbol, using C++ CRT initialization as SoH does.
#include <string.h>

static float XboxFloatBits(unsigned int bits) {
    typedef char uint_and_float_are_32_bits[(sizeof(bits) == 4 && sizeof(float) == 4) ? 1 : -1];
    (void)sizeof(uint_and_float_are_32_bits);
    float value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

extern "C" {
float __libm_qnan_f = XboxFloatBits(0x7fc00000u);
}
