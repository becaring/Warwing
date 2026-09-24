#pragma once
#include <string>
#include "fast/backends/gfx_rendering_api.h"
#include "fast/cc_features.h"

bool Shipyard_BuildFast3DShader(const Fast::ShaderProgramKey& key,
                               CCFeatures& features,size_t& numFloats,
                               std::string& hlsl,std::string& error);

// Syntax lowering only, after authoritative Prism generation. Arithmetic,
// alpha thresholds, wrapping, masks and user source remain unchanged.
bool Shipyard_LowerShader(const std::string& hlsl, std::string& lowered,
                         std::string& error);
