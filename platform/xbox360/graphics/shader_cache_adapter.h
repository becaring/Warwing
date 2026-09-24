#pragma once
#include <string>

struct Smash360ShaderCounts {unsigned entries,hits,misses,compiled,writes,bytes;};
void Smash360_GetShaderCounts(Smash360ShaderCounts* counts);
bool Smash360_WriteShaderCacheRecord(const std::string& record,bool truncate);
