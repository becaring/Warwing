#pragma once
#include <stdint.h>
#ifndef SMASH360_ENABLE_FULL_PROFILING
#define SMASH360_ENABLE_FULL_PROFILING 1
#endif
#ifndef SMASH360_PERF_HOST_TEST
#include <ppcintrinsics.h>
#endif

// Adapted from SoH360 platform/xbox360/perf_trace.h: Xenon low time-base word,
// thread-owned samples and RAII scopes. No gameplay clocks use this counter.
// Unsigned subtraction handles rollover for individual scopes below ~85s.
#define SMASH360_PERF_SECTIONS(X) \
    X(FAST3D, fast3d_run) X(FRAME_SETUP, frame_setup) X(COMPOSE, compose) \
    X(MATRIX, rsp_matrix) X(VERTEX, rsp_vertex) X(TRIANGLE, rdp_triangle) \
    X(FLUSH, batch_flush) X(TEXTURE_IMPORT, texture_import) \
    X(TEXTURE_CACHE, texture_cache) X(TEXTURE_HASH, texture_hash) \
    X(TEXTURE_INVALIDATE, texture_invalidate) X(COMBINER, combiner_lookup) \
    X(SHADER_LOOKUP, shader_lookup) X(DL_NORMALIZE, dl_normalize) \
    X(POINTER_CHECK, pointer_check) X(DL_STEP, command_step) X(DL_BOUNDS, dl_bounds) X(GBI_TRACE, gbi_trace) \
    X(DRAW, native_draw) X(DRAW_UP, draw_primitive_up) \
    X(UPLOAD, texture_upload) X(TEXTURE_CREATE, texture_create) X(TEXTURE_LOCK, texture_lock) \
    X(TEXTURE_COLLECT, texture_collect) X(TEXTURE_RELEASE, texture_release) \
    X(STORE, framebuffer_store) X(RESTORE, framebuffer_restore) X(RESTORE_QUAD, restore_quad) \
    X(FRAMEBUFFER_UPDATE, framebuffer_update) X(DEPTH, depth_read) X(DEPTH_WAIT, depth_lock) \
    X(GPU_IDLE, explicit_gpu_idle) X(END_TILING, end_tiling) \
    X(SHADER, shader_create) X(SHADER_BUILD, shader_build) X(SHADER_LOWER, shader_lower) \
    X(SHADER_CODE, shader_code) X(SHADER_COMPILE, shader_compile) \
    X(GUI_START, gui_start) X(GUI_END, gui_end) X(GUI_RENDER, gui_native_render) \
    X(NATIVE_END, native_end) X(NATIVE_FINISH, native_finish) \
    X(INSTANCE_ACQUIRE, interpreter_owner) X(RELOC_RANGE, reloc_range_lookup) \
    X(RELOC_ID, reloc_id_lookup) X(RELOC_VERTEX, reloc_vertex_fixup) \
    X(RELOC_TEXTURE, reloc_texture_fixup) X(BOUNDS_GENERATION, bounds_generation) \
    X(BOUNDS_SCAN, bounds_locked_scan)
#define SMASH360_PERF_COUNTERS(X) \
    X(COMMANDS, commands) X(VERTICES, vertices) X(TRIANGLES, triangle_requests) \
    X(DRAW_TRIANGLES, submitted_triangles) X(DRAW_BYTES, submitted_vertex_bytes) \
    X(TEXTURE_HITS, texture_hits) X(TEXTURE_MISSES, texture_misses) \
    X(TEXTURE_STALE, texture_stale) X(HASH_BYTES, texture_hash_bytes) \
    X(UPLOAD_BYTES, upload_requested_bytes) X(NATIVE_BINDS, native_texture_binds) \
    X(BOUNDS_HIT, bounds_cache_hits) X(BOUNDS_MISS, bounds_cache_misses) \
    X(BOUNDS_VISITS, bounds_scan_entries) X(BOUNDS_FOUND, bounds_scan_found) \
    X(BOUNDS_UNKNOWN, bounds_unknown) X(BOUNDS_PAST, bounds_walked_past) \
    X(BOUNDS_UNKNOWN_HIT, bounds_unknown_hits)
#define SMASH360_SECTION_ENUM(id, label) SMASH_PERF_##id,
enum Smash360PerfSection { SMASH360_PERF_SECTIONS(SMASH360_SECTION_ENUM)
    SMASH_PERF_OPCODE_BASE, SMASH_PERF_COUNT = SMASH_PERF_OPCODE_BASE + 256 };
#undef SMASH360_SECTION_ENUM
#define SMASH360_COUNTER_ENUM(id, label) SMASH_COUNT_##id,
enum Smash360PerfCount { SMASH360_PERF_COUNTERS(SMASH360_COUNTER_ENUM) SMASH_COUNT_COUNT };
#undef SMASH360_COUNTER_ENUM

struct Smash360PerfSample { uint64_t ticks, self; unsigned calls; uint32_t maximum; };
struct Smash360PerfScope;
extern bool smash360_perf_enabled;
extern bool smash360_perf_detail;
__forceinline Smash360PerfSection Smash360_OpcodeSection(uint8_t opcode) {
    return static_cast<Smash360PerfSection>(SMASH_PERF_OPCODE_BASE + opcode);
}
extern __declspec(thread) Smash360PerfSample smash360_perf_samples[SMASH_PERF_COUNT + 1];
extern __declspec(thread) uint64_t smash360_perf_counts[SMASH_COUNT_COUNT];
extern __declspec(thread) Smash360PerfScope* smash360_perf_parent;
#ifdef SMASH360_PERF_HOST_TEST
uint32_t Smash360_PerfCounter();
#else
__forceinline uint32_t Smash360_PerfCounter() { return __mftb32(); }
#endif
__forceinline void Smash360_PerfCount(Smash360PerfCount counter, unsigned value = 1) {
#if SMASH360_ENABLE_FULL_PROFILING
    if (smash360_perf_enabled) smash360_perf_counts[counter] += value;
#endif
}
__forceinline void Smash360_PerfDetailCount(Smash360PerfCount counter) {
    if (smash360_perf_detail) Smash360_PerfCount(counter);
}

// Inclusive wall time plus self time excluding nested instrumented scopes.
// SDK calls can wait for the GPU: neither column is GPU execution time or pure
// CPU time. Same-section recursion contributes each call to the inclusive sum.
struct Smash360PerfScope {
#if SMASH360_ENABLE_FULL_PROFILING
    Smash360PerfSection section;
    uint32_t start;
    uint64_t children;
    Smash360PerfScope* parent;
    bool active;
    __forceinline Smash360PerfScope(Smash360PerfSection value, bool enabled = true)
        : section(value), children(0), active(smash360_perf_enabled && enabled) {
        if (active) {
            parent = smash360_perf_parent;
            smash360_perf_parent = this;
            start = Smash360_PerfCounter();
        }
    }
    __forceinline ~Smash360PerfScope() {
        if (!active) return;
        const uint32_t elapsed = Smash360_PerfCounter() - start;
        Smash360PerfSample& sample = smash360_perf_samples[section];
        sample.ticks += elapsed;
        sample.self += elapsed - children;
        ++sample.calls;
        if (elapsed > sample.maximum) sample.maximum = elapsed;
        smash360_perf_parent = parent;
        if (parent) parent->children += elapsed;
    }
#else
    __forceinline Smash360PerfScope(Smash360PerfSection, bool = true) {}
    __forceinline ~Smash360PerfScope() {}
#endif
  private:
    Smash360PerfScope(const Smash360PerfScope&);
    Smash360PerfScope& operator=(const Smash360PerfScope&);
};

struct Smash360NativePerf {
    unsigned samplerAttempted, samplerWritten, samplerSuppressed;
    unsigned constantsAttempted, constantsWritten, constantsSuppressed;
    unsigned bindingAttempted, bindingWritten, bindingSuppressed;
    unsigned uploadRequests, uploadReused, uploadSavedBytes;
    unsigned clears, restoresAvoided, depthRestoresAvoided;
    unsigned pendingTextures, pendingBytes, width, height, samples, tiles;
};
namespace Fast { void CaptureNativePerf(Smash360NativePerf*); }
void Smash360_InitPerf();
void Smash360_ResetPerf();
void Smash360_ReportPerf(unsigned frames, double elapsed, double logic, double render, double present);
