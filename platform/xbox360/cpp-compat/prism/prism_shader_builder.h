#pragma once
#include "shader_provider.h"

// Implement through Ship::ResourceManager LoadResource(path,true,init), with
// type Shader, Native byte order and Binary format, then copy the raw string.
// False means resource absent/failed; no disk/fabricated shader fallback here.
bool Smash360_LoadShaderResource(const std::string& path,std::string& source);
namespace Fast {
const char* gfx_get_shader(int16_t shaderId);
std::string gfx_direct3d_common_build_shader(size_t& numFloats,
    const CCFeatures& features,bool rootSignature,bool threePoint,bool srgb);
}
