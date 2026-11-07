#include "runtime.h"
#include "perf_trace.h"
#include "triangle_trace.h"
#include "command_trace.h"
#include "../environment.h"
#include "shader_cache_adapter.h"
#include <string.h>

// The renderer's calling thread alone snapshots/resets its samples. The donor
// diagnostic worker only sees copied bytes, never live renderer containers.
bool smash360_perf_enabled;
bool smash360_perf_detail;
bool smash360_triangle_trace;
__declspec(thread) SmashTriangleSamples smash360_triangle_samples;
__declspec(thread) uint32_t smash360_triangle_random=0xA361CB27;
bool smash360_command_trace;
__declspec(thread) SmashCommandSamples smash360_command_samples;
__declspec(thread) uint32_t smash360_command_random=0x8f315a27;
__declspec(thread) Smash360PerfSample smash360_perf_samples[SMASH_PERF_COUNT + 1];
__declspec(thread) uint64_t smash360_perf_counts[SMASH_COUNT_COUNT];
__declspec(thread) Smash360PerfScope* smash360_perf_parent;
namespace {
#define SECTION_NAME(id, label) #label,
const char* sections[] = { SMASH360_PERF_SECTIONS(SECTION_NAME) };
#undef SECTION_NAME
#define COUNTER_NAME(id, label) #label,
const char* counters[] = { SMASH360_PERF_COUNTERS(COUNTER_NAME) };
#undef COUNTER_NAME
struct Snapshot {
    unsigned window, frames;
    bool detail;
    double elapsed, logic, render, present, frequency;
    Smash360PerfSample samples[SMASH_PERF_COUNT];
    uint64_t counts[SMASH_COUNT_COUNT];
    uint32_t observer;
    Smash360NativePerf native;
    Smash360ShaderCounts shader;
};
unsigned windowNumber;
void Format(const void* bytes, Smash360DiagnosticEmit emit) {
    Snapshot s;
    memcpy(&s, bytes, sizeof(s)); // The donor transport's byte buffer need not be aligned.
    const double ms = 1000.0 / (s.frequency * s.frames);
    emit("PERF window=%u frames=%u elapsed=%.3f logic_ms=%.3f render_ms=%.3f present_ms=%.3f inclusive_wall_and_self_ms_per_frame",
         s.window, s.frames, s.elapsed, s.logic*1000/s.frames, s.render*1000/s.frames, s.present*1000/s.frames);
    uint64_t calls = 0, self = 0;
    for (unsigned i=0; i<SMASH_PERF_COUNT; ++i) {
        const Smash360PerfSample& v = s.samples[i];
        calls += v.calls; self += v.self;
        if (v.calls && i<SMASH_PERF_OPCODE_BASE) emit("PERF section=%s inclusive_ms=%.3f self_ms=%.3f calls_per_frame=%.2f max_call_ms=%.3f",
                         sections[i], v.ticks*ms, v.self*ms, double(v.calls)/s.frames, v.maximum*1000.0/s.frequency);
    }
    // Rank raw opcode bytes without guessing which microcode/scene used them.
    // All 256 slots are measured, but only the busiest eight are printed.
    if(s.detail) {
        bool printed[256] = {};
        for(unsigned rank=0;rank<8;++rank) {
            int best=-1;
            for(unsigned opcode=0;opcode<256;++opcode) {
                const Smash360PerfSample& v=s.samples[SMASH_PERF_OPCODE_BASE+opcode];
                if(!printed[opcode] && v.calls && (best<0 || v.self>s.samples[SMASH_PERF_OPCODE_BASE+best].self))best=opcode;
            }
            if(best<0)break;
            printed[best]=true;
            const Smash360PerfSample& v=s.samples[SMASH_PERF_OPCODE_BASE+best];
            emit("PERF opcode=%02X inclusive_ms=%.3f self_ms=%.3f calls_per_frame=%.2f max_call_ms=%.3f",
                 best,v.ticks*ms,v.self*ms,double(v.calls)/s.frames,v.maximum*1000.0/s.frequency);
        }
        uint64_t remainderSelf=0,remainderCalls=0;
        for(unsigned opcode=0;opcode<256;++opcode)if(!printed[opcode]) {
            remainderSelf+=s.samples[SMASH_PERF_OPCODE_BASE+opcode].self;
            remainderCalls+=s.samples[SMASH_PERF_OPCODE_BASE+opcode].calls;
        }
        emit("PERF opcode_other self_ms=%.3f calls_per_frame=%.2f",remainderSelf*ms,double(remainderCalls)/s.frames);
    }
    for (unsigned i=0; i<SMASH_COUNT_COUNT; ++i)
        emit("PERF count=%s per_frame=%.2f", counters[i], double(s.counts[i])/s.frames);
    const double observer = double(s.observer)/s.frequency/1024;
    emit("PERF observer ns_per_scope=%.1f scopes_per_frame=%.2f estimated_ms_per_frame=%.3f measured_self_ms=%.3f",
         observer*1e9, double(calls)/s.frames, observer*calls*1000/s.frames, self*ms);
    const Smash360NativePerf& n = s.native;
    emit("PERF native_state sampler_attempted=%u sampler_written=%u sampler_suppressed=%u constants_attempted=%u constants_written=%u constants_suppressed=%u binding_attempted=%u binding_written=%u binding_suppressed=%u",
         n.samplerAttempted,n.samplerWritten,n.samplerSuppressed,n.constantsAttempted,n.constantsWritten,n.constantsSuppressed,
         n.bindingAttempted,n.bindingWritten,n.bindingSuppressed);
    emit("PERF uploads requests=%u reused=%u saved_bytes=%u pending_textures=%u pending_bytes=%u",
         n.uploadRequests,n.uploadReused,n.uploadSavedBytes,n.pendingTextures,n.pendingBytes);
    emit("PERF framebuffer width=%u height=%u samples=%u tiles=%u clears=%u restores_avoided=%u depth_restores_avoided=%u",
         n.width,n.height,n.samples,n.tiles,n.clears,n.restoresAvoided,n.depthRestoresAvoided);
    emit("PERF shader_cache cumulative=1 entries=%u hits=%u misses=%u compiled=%u queued_writes=%u bytes=%u",
         s.shader.entries,s.shader.hits,s.shader.misses,s.shader.compiled,s.shader.writes,s.shader.bytes);
    emit("PERF end window=%u", s.window);
}
}
void Smash360_ResetPerf() {
    if (smash360_perf_parent) Smash360_Fatal("profiler reset inside active scope", E_FAIL);
    memset(smash360_perf_samples, 0, sizeof(smash360_perf_samples));
    memset(smash360_perf_counts, 0, sizeof(smash360_perf_counts));
    Smash360NativePerf ignored; Fast::CaptureNativePerf(&ignored);
}
void Smash360_InitPerf() {
    const char* triangle = XboxEnv_Get("WARWING_TRIANGLE_TRACE");
    smash360_triangle_trace = triangle && triangle[0]=='1';
    const char* command = XboxEnv_Get("WARWING_COMMAND_TRACE");
    smash360_command_trace = command && command[0]=='1';
    const char* mode = XboxEnv_Get("WARWING_PROFILE");
    smash360_perf_enabled = SMASH360_ENABLE_FULL_PROFILING && (!mode || mode[0]!='0');
    const char* detail = XboxEnv_Get("WARWING_PROFILE_DETAIL");
    smash360_perf_detail = smash360_perf_enabled && detail && detail[0]=='1';
    // Same unit/epoch validation as SoH's direct-counter bring-up check.
    LARGE_INTEGER before, after;
    QueryPerformanceCounter(&before);
    const uint32_t direct = Smash360_PerfCounter();
    QueryPerformanceCounter(&after);
    if (direct-uint32_t(before.QuadPart) > uint32_t(after.QuadPart-before.QuadPart))
        Smash360_Fatal("profiler counter/QPC units", E_FAIL);
    Smash360_Log("PERF schema=2 enabled=%d detail=%d donor=SoH360 thread_local=1 report_seconds=5 self_excludes_instrumented_children=1",
                 smash360_perf_enabled,smash360_perf_detail);
    Smash360_Log("TRI_TRACE enabled=%d sample_probability=1/64 estimates_include_probe_overhead=1",smash360_triangle_trace);
    Smash360_Log("PERF full_scopes_compiled=%d",SMASH360_ENABLE_FULL_PROFILING);
    Smash360_Log("CMD_TRACE enabled=%d sample_probability=1/128 estimates_include_probe_overhead=1",smash360_command_trace);
}

void Smash360_ReportCommandTrace(unsigned frames) {
    if(!smash360_command_trace || !frames)return;
    const SmashCommandSamples snapshot=smash360_command_samples;
    memset(&smash360_command_samples,0,sizeof(smash360_command_samples));
    LARGE_INTEGER frequency;QueryPerformanceFrequency(&frequency);
    const double measuredScale=1000.0/(double(frequency.QuadPart)*frames);
    const double scale=snapshot.sampled?measuredScale*snapshot.calls/snapshot.sampled:0;
    static const char* names[]={"loop_debug","command_fetch","bounds","trace_callback","dispatch_handler"};
    Smash360_Log("CMD_TRACE frames=%u walks=%u calls=%u sampled=%u calls_per_frame=%.2f setup_ms=%.3f walk_ms=%.3f finish_ms=%.3f",
        frames,snapshot.walks,snapshot.calls,snapshot.sampled,double(snapshot.calls)/frames,
        snapshot.walkTicks[0]*measuredScale,snapshot.walkTicks[1]*measuredScale,snapshot.walkTicks[2]*measuredScale);
    for(unsigned i=0;i<SMASH_CMD_PHASES;++i)
        Smash360_Log("CMD_TRACE phase=%s estimated_ms_per_frame=%.3f sampled_ticks=%I64u",names[i],snapshot.ticks[i]*scale,snapshot.ticks[i]);
    for(unsigned i=0;i<256;++i)if(snapshot.opcodeSamples[i])
        Smash360_Log("CMD_TRACE opcode=%02X handler_estimated_ms_per_frame=%.3f sampled=%u sampled_ticks=%I64u",
            i,snapshot.opcodeTicks[i]*scale,snapshot.opcodeSamples[i],snapshot.opcodeTicks[i]);
}

void Smash360_ReportTriangleTrace(unsigned frames) {
    Smash360_ReportCommandTrace(frames);
    if(!smash360_triangle_trace || !frames)return;
    const SmashTriangleSamples snapshot=smash360_triangle_samples;
    memset(&smash360_triangle_samples,0,sizeof(smash360_triangle_samples));
    static const char* names[]={"cull","raster_state","combiner","texture_state","shader_state",
        "depth_diag","rcp_area","vertex_pack","finish_flush"};
    LARGE_INTEGER frequency;QueryPerformanceFrequency(&frequency);
    // Estimate cost using the observed sampling fraction, including culled
    // triangles. Never divide by phase visits (which would inflate rare paths).
    const double scale=snapshot.sampled?1000.0*snapshot.calls/(double(frequency.QuadPart)*snapshot.sampled*frames):0;
    Smash360_Log("TRI_TRACE frames=%u calls=%u sampled=%u calls_per_frame=%.2f",
        frames,snapshot.calls,snapshot.sampled,double(snapshot.calls)/frames);
    for(unsigned i=0;i<SMASH_TRI_PHASES;++i)
        Smash360_Log("TRI_TRACE phase=%s estimated_ms_per_frame=%.3f sampled_visits=%u sampled_ticks=%I64u",
            names[i],snapshot.ticks[i]*scale,snapshot.visits[i],snapshot.ticks[i]);
}
void Smash360_ReportPerf(unsigned frames, double elapsed, double logic, double render, double present) {
    if (!smash360_perf_enabled || !frames) return;
    if (smash360_perf_parent) Smash360_Fatal("profiler report inside active scope", E_FAIL);
    const uint32_t captureStart = Smash360_PerfCounter();
    Snapshot s;
    s.window=++windowNumber; s.frames=frames; s.elapsed=elapsed; s.detail=smash360_perf_detail;
    s.logic=logic; s.render=render; s.present=present;
    LARGE_INTEGER frequency; QueryPerformanceFrequency(&frequency); s.frequency=double(frequency.QuadPart);
    memcpy(s.samples,smash360_perf_samples,sizeof(s.samples));
    memcpy(s.counts,smash360_perf_counts,sizeof(s.counts));
    const uint32_t begin=Smash360_PerfCounter();
    for(unsigned i=0;i<1024;++i) {Smash360PerfScope probe(SMASH_PERF_COUNT);}
    s.observer=Smash360_PerfCounter()-begin;
    Smash360_GetShaderCounts(&s.shader);
    Fast::CaptureNativePerf(&s.native);
    memset(smash360_perf_samples,0,sizeof(smash360_perf_samples));
    memset(smash360_perf_counts,0,sizeof(smash360_perf_counts));
    Smash360_QueueDiagnostic(Format,&s,sizeof(s),captureStart);
}
