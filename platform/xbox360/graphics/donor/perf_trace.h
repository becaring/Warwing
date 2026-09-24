#pragma once
#include <stdint.h>
#include <ppcintrinsics.h>

// Each thread owns its samples; the game thread reports only its own costs.
// Timings are inclusive wall time: Fast3D
// contains native draw/upload/resolve calls, and native calls may wait on GPU.
enum SoHPerfSection {
    SOH_PERF_INTERPOLATION,SOH_PERF_FAST3D,SOH_PERF_DRAW,SOH_PERF_UPLOAD,
    SOH_PERF_STORE,SOH_PERF_RESTORE,SOH_PERF_DEPTH,SOH_PERF_DEPTH_WAIT,
    SOH_PERF_GUI_BUILD,SOH_PERF_GUI_RENDER,SOH_PERF_SHADER,
    SOH_PERF_RECORD_ROTATE,SOH_PERF_MATRIX,SOH_PERF_VERTEX,SOH_PERF_TRIANGLE,
    SOH_PERF_TEXTURE_IMPORT,SOH_PERF_RESOURCE,SOH_PERF_CVAR,
    SOH_PERF_CONFIG_LOCK,SOH_PERF_RECORD_ALLOC,SOH_PERF_RECORD_FREE,
    SOH_PERF_VERTEX_POSITION,SOH_PERF_LIGHT_PREP,SOH_PERF_GAMEPLAY_UPDATE,SOH_PERF_GAMEPLAY_DRAW,
    SOH_PERF_VERTEX_ATTRIBUTES,
#ifdef SOH_TRIANGLE_DETAIL
    SOH_PERF_TRIANGLE_CULL,SOH_PERF_TRIANGLE_PIPELINE,SOH_PERF_TRIANGLE_PACK,
#endif
    SOH_PERF_COUNT
};
#ifndef SOH_TRIANGLE_DETAIL
static const SoHPerfSection SOH_PERF_TRIANGLE_CULL=SOH_PERF_COUNT;
static const SoHPerfSection SOH_PERF_TRIANGLE_PIPELINE=SOH_PERF_COUNT;
static const SoHPerfSection SOH_PERF_TRIANGLE_PACK=SOH_PERF_COUNT;
#endif
struct SoHVertexCounts {
    unsigned batches,vertices,vector_vertices,lit_vertices,texgen_vertices,linear_vertices,fog_vertices;
    unsigned shade_reused,texgen_reused;
    unsigned shade_cross_batch,shade_verified;
    unsigned lit_fog_fast;
    unsigned attributes_deferred,attributes_materialized,attributes_discarded,attributes_verified;
};
void SoH_GetVertexCounts(SoHVertexCounts*);
struct SoHTextureBindingCounts {unsigned requests,reused,changed;};
void SoH_GetTextureBindingCounts(SoHTextureBindingCounts*);
struct SoHTextureUploadCounts { unsigned requests,reused,verified,bytes_saved; };
void SoH_GetTextureUploadCounts(SoHTextureUploadCounts*);
struct SoHNativeStateCounts {
    unsigned sampler_attempted,sampler_written,sampler_suppressed;
    unsigned constants_attempted,constants_written,constants_suppressed;
    unsigned sampler_verified,constants_verified;
};
void SoH_GetNativeStateCounts(SoHNativeStateCounts*);
bool SoH_VerifyFast3DReuse();
void SoH_FailFast3DReuse();
void SoH_AdvanceFast3DVerification();
void SoH_RestartFast3DVerification();
// The SDK recommends the low word to avoid Xenon's transient high-word read
// at rollover. Unsigned subtraction handles rollover for scopes under ~85 s.
// These are short diagnostic scopes; gameplay clocks/pacing still use QPC.
inline uint32_t SoH_PerfCounter() {return __mftb32();}
struct SoHPerfSample { uint64_t ticks;unsigned calls; };
extern __declspec(thread) SoHPerfSample soh_perf_samples[SOH_PERF_COUNT+1];
extern __declspec(thread) unsigned soh_triangle_timing_pairs;
// Preserve every sample, including the observer probe. Inlining this small
// thread-local update removes a call/return from each instrumented hot scope.
__forceinline void SoH_PerfRecord(SoHPerfSection section,uint32_t start) {
    const uint32_t elapsed=SoH_PerfCounter()-start;
    SoHPerfSample& sample=soh_perf_samples[section];sample.ticks+=elapsed;++sample.calls;
}
struct SoHProfileWindow {
    unsigned updates;
    int scene,pause,rate;
    double elapsed,logic,render,present,audioWait;
};
void SoH_PerfReport(const SoHProfileWindow&);
struct SoHPerfScope {
    SoHPerfSection section;
    uint32_t start;
    SoHPerfScope(SoHPerfSection value):section(value),start(SoH_PerfCounter()){}
    ~SoHPerfScope(){SoH_PerfRecord(section,start);}
};

// Opt-in encounter diagnostic. Stop before entering another measured phase;
// the destructor also accounts for early triangle rejection.
extern bool soh_triangle_detail_enabled;
struct SoHTriangleDetailScope {
#ifdef SOH_TRIANGLE_DETAIL
    SoHPerfSection section;
    uint32_t start;
    bool active;
    SoHTriangleDetailScope(SoHPerfSection value):section(value),start(0),active(soh_triangle_detail_enabled) {
        if(active)start=SoH_PerfCounter();
    }
    __forceinline void Stop() {
        if(active) {SoH_PerfRecord(section,start);active=false;}
    }
    ~SoHTriangleDetailScope(){Stop();}
#else
    // Production builds pay no per-triangle diagnostic branches or live state.
    // Define SOH_TRIANGLE_DETAIL for the archived three-phase diagnostic mode.
    SoHTriangleDetailScope(SoHPerfSection){}
    __forceinline void Stop(){}
#endif
};
void SoH_GetTrianglePipelineCounts(unsigned*,unsigned*,unsigned*);
