#include "shader_cache_adapter.h"
#include "xenos/shader_cache.h"

void Smash360_GetShaderCounts(Smash360ShaderCounts* counts) {
    if(!counts)return;
    Shipyard::Xenos::ShaderCacheCounts current;
    Shipyard::Xenos::GetShaderCacheCounts(&current);
    counts->entries=current.entries;
    counts->hits=current.hits;
    counts->misses=current.misses;
    counts->compiled=current.compiled;
    counts->writes=current.writes;
    counts->bytes=current.bytes;
}
bool Smash360_WriteShaderCacheRecord(const std::string& record,bool truncate) {
    return Shipyard::Xenos::WriteShaderCacheRecord(record,truncate);
}
