#pragma once
#include "perf_trace.h"
// Sample real production triangles, independently of the expensive full
// profiler. The same Xenon time-base primitive is inherited from SoH360.
enum SmashTrianglePhase { SMASH_TRI_CULL, SMASH_TRI_STATE, SMASH_TRI_COMBINER,
    SMASH_TRI_TEXTURE, SMASH_TRI_SHADER, SMASH_TRI_DIAGNOSTIC, SMASH_TRI_AREA,
    SMASH_TRI_PACK, SMASH_TRI_FINISH, SMASH_TRI_PHASES };
struct SmashTriangleSamples {
    uint64_t ticks[SMASH_TRI_PHASES];
    unsigned visits[SMASH_TRI_PHASES], calls, sampled;
};
extern bool smash360_triangle_trace;
extern __declspec(thread) SmashTriangleSamples smash360_triangle_samples;
extern __declspec(thread) uint32_t smash360_triangle_random;
struct SmashTriangleTrace {
    bool active;
    unsigned phase;
    uint32_t start;
    __forceinline SmashTriangleTrace() : active(false) {
        if (!smash360_triangle_trace) return;
        ++smash360_triangle_samples.calls;
        // Nonzero xorshift state: avoid repeatedly selecting the same model
        // command when a scene submits a fixed number of triangles each frame.
        uint32_t x=smash360_triangle_random;
        x^=x<<13;x^=x>>17;x^=x<<5;smash360_triangle_random=x;
        active=(x&63)==0;
        if(active) {++smash360_triangle_samples.sampled;phase=SMASH_TRI_CULL;start=Smash360_PerfCounter();}
    }
    __forceinline void Mark(unsigned next) {
        if(!active)return;
        uint32_t now=Smash360_PerfCounter();
        smash360_triangle_samples.ticks[phase]+=uint32_t(now-start);
        ++smash360_triangle_samples.visits[phase];phase=next;start=now;
    }
    __forceinline ~SmashTriangleTrace() {if(active)Mark(phase);}
private:
    SmashTriangleTrace(const SmashTriangleTrace&);
    SmashTriangleTrace& operator=(const SmashTriangleTrace&);
};
void Smash360_ReportTriangleTrace(unsigned frames);
