#include "fast3d/vertex_lighting.h"
extern "C" __declspec(noinline) float NormalOriginal(int8_t value) { return (float)value; }
extern "C" __declspec(noinline) float NormalProjected(int8_t value) { return Smash360Fast::NormalByteFloat(value); }
extern "C" __declspec(noinline) float LightOriginal(uint8_t value) { return (float)value; }
extern "C" __declspec(noinline) float LightProjected(uint8_t value) { return Smash360Fast::LightByteFloat(value); }
extern "C" __declspec(noinline) float TruncateOriginal(float value) { return (float)(int32_t)value; }
extern "C" __declspec(noinline) float TruncateProjected(float value) { return Smash360Fast::TruncateLightChannel(value); }
