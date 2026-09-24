#define SMASH360_PERF_HOST_TEST
#include "runtime/perf_trace.h"
#include "runtime/triangle_trace.h"
#include <assert.h>
#include <stdio.h>

bool smash360_perf_enabled = true;
bool smash360_perf_detail = true;
__declspec(thread) Smash360PerfSample smash360_perf_samples[SMASH_PERF_COUNT + 1];
__declspec(thread) uint64_t smash360_perf_counts[SMASH_COUNT_COUNT];
__declspec(thread) Smash360PerfScope* smash360_perf_parent;
static uint32_t now;
bool smash360_triangle_trace;
__declspec(thread) SmashTriangleSamples smash360_triangle_samples;
__declspec(thread) uint32_t smash360_triangle_random=0xA361CB27;
uint32_t Smash360_PerfCounter() { return now; }

static void EarlyReturn() {
    Smash360PerfScope scope(SMASH_PERF_VERTEX);
    now += 3;
    return;
}
int main() {
    now = 10;
    {
        Smash360PerfScope root(SMASH_PERF_FAST3D);
        now = 20;
        { Smash360PerfScope child(SMASH_PERF_VERTEX); now = 25; }
        // Recursion must not double-charge child time to exclusive totals.
        { Smash360PerfScope child(SMASH_PERF_FAST3D); now = 30; }
        EarlyReturn();
        now = 40;
    }
    assert(!smash360_perf_parent);
    assert(smash360_perf_samples[SMASH_PERF_FAST3D].ticks == 35);
    assert(smash360_perf_samples[SMASH_PERF_FAST3D].self == 22);
    assert(smash360_perf_samples[SMASH_PERF_FAST3D].calls == 2);
    assert(smash360_perf_samples[SMASH_PERF_FAST3D].maximum == 30);
    assert(smash360_perf_samples[SMASH_PERF_VERTEX].self == 8);
    assert(smash360_perf_samples[SMASH_PERF_VERTEX].calls == 2);
    now = 0xfffffffeu;
    { Smash360PerfScope wrap(SMASH_PERF_UPLOAD); now = 3; }
    assert(smash360_perf_samples[SMASH_PERF_UPLOAD].ticks == 5);
    smash360_perf_enabled = false;
    { Smash360PerfScope off(SMASH_PERF_UPLOAD); now += 20; }
    Smash360_PerfCount(SMASH_COUNT_VERTICES, 10);
    assert(smash360_perf_samples[SMASH_PERF_UPLOAD].calls == 1);
    assert(smash360_perf_counts[SMASH_COUNT_VERTICES] == 0);
    smash360_perf_enabled = true;
    Smash360_PerfCount(SMASH_COUNT_VERTICES, 10);
    assert(smash360_perf_counts[SMASH_COUNT_VERTICES] == 10);
    // Optional inner scopes must not steal time or the parent link when off.
    now = 100;
    {
        Smash360PerfScope outer(SMASH_PERF_GUI_START);
        now = 105;
        { Smash360PerfScope disabled(SMASH_PERF_INSTANCE_ACQUIRE, false);
          now = 110; assert(smash360_perf_parent == &outer); }
        now = 112;
    }
    assert(smash360_perf_samples[SMASH_PERF_INSTANCE_ACQUIRE].calls == 0);
    assert(smash360_perf_samples[SMASH_PERF_GUI_START].self == 12);
    // Raw high-bit command bytes must address their own section, not sign-extend.
    now = 200;
    {
        Smash360PerfScope opcode(Smash360_OpcodeSection(0xdb), true);
        now = 204;
        { Smash360PerfScope acquire(SMASH_PERF_INSTANCE_ACQUIRE, true); now = 207; }
        now = 210;
    }
    assert(smash360_perf_samples[SMASH_PERF_OPCODE_BASE+0xdb].calls == 1);
    assert(smash360_perf_samples[SMASH_PERF_OPCODE_BASE+0xdb].ticks == 10);
    assert(smash360_perf_samples[SMASH_PERF_OPCODE_BASE+0xdb].self == 7);
    assert(smash360_perf_samples[SMASH_PERF_INSTANCE_ACQUIRE].self == 3);
    assert(!smash360_perf_parent);
    puts("PASS actual profiler: nesting, recursion, early return, rollover, disabled mode and counters");
    {SmashTriangleTrace off;off.Mark(SMASH_TRI_PACK);}
    assert(smash360_triangle_samples.calls==0);
    smash360_triangle_trace=true;
    for(unsigned i=0;i<65536;++i) {
        now=0xfffffffeu;
        SmashTriangleTrace trace;
        now=3;trace.Mark(SMASH_TRI_STATE);
        now=10;trace.Mark(SMASH_TRI_PACK);
        now=21;
    }
    const unsigned sampled=smash360_triangle_samples.sampled;
    assert(smash360_triangle_samples.calls==65536 && sampled>800 && sampled<1250);
    assert(smash360_triangle_samples.ticks[SMASH_TRI_CULL]==uint64_t(sampled)*5);
    assert(smash360_triangle_samples.ticks[SMASH_TRI_STATE]==uint64_t(sampled)*7);
    assert(smash360_triangle_samples.ticks[SMASH_TRI_PACK]==uint64_t(sampled)*11);
    assert(smash360_triangle_samples.visits[SMASH_TRI_PACK]==sampled);
    assert(smash360_triangle_samples.visits[SMASH_TRI_SHADER]==0);
    // A sampled early return must charge the current phase without requiring
    // later marks; an unselected call contributes no timing.
    unsigned before=sampled;
    while(smash360_triangle_samples.sampled==before) {now=30;SmashTriangleTrace trace;now=39;}
    assert(smash360_triangle_samples.visits[SMASH_TRI_CULL]==sampled+1);
    assert(smash360_triangle_samples.ticks[SMASH_TRI_CULL]==uint64_t(sampled)*5+9);
    puts("PASS triangle sampling: disabled path, selection, phase accounting, rollover and early return");
}
