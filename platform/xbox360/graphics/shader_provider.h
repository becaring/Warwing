#pragma once
#include <string>
#include "fast/backends/gfx_rendering_api.h"
#include "fast/cc_features.h"
#include "graphics/shader_lower.h"

bool Shipyard_BuildFast3DShader(const Fast::ShaderProgramKey& key,
                               CCFeatures& features,size_t& numFloats,
                               std::string& hlsl,std::string& error);
