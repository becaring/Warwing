#define SMASH360_PERF_HOST_TEST
#include "runtime/command_trace.h"
#include "runtime/frame_workload.h"
#include <assert.h>
#include <stdio.h>
bool smash360_command_trace;
__declspec(thread) SmashCommandSamples smash360_command_samples;
__declspec(thread) uint32_t smash360_command_random=0x8f315a27;
static uint32_t clockValue;
uint32_t Smash360_PerfCounter() { return clockValue; }
int main() {
    SmashFrameWorkload workload={};
    workload.Add(1023,0.02,0.003,0.015,0.002);
    workload.Add(1024,0.01,0.002,0.006,0.002);
    workload.Add(14336,0.02,0.003,0.015,0.002);
    workload.Add(15359,0.02,0.003,0.015,0.002);
    workload.Add(0xffffffffu,0.1,0.01,0.08,0.01);
    assert(workload.bands[0].frames==1 && workload.bands[1].frames==1);
    assert(workload.bands[14].frames==2 && workload.bands[31].frames==1);
    assert(workload.bands[14].elapsed==0.04 && workload.bands[14].render==0.03);
    assert(workload.bands[14].frames/workload.bands[14].elapsed==50.0);
    workload.Reset();
    for(unsigned i=0;i<SmashFrameWorkload::Count;++i) {
        assert(!workload.bands[i].frames && !workload.bands[i].elapsed &&
               !workload.bands[i].logic && !workload.bands[i].render && !workload.bands[i].present);
    }
    { SmashCommandTrace off; clockValue+=9; off.Mark(SMASH_CMD_BOUNDS); off.Opcode(0xDE); }
    assert(smash360_command_samples.calls==0);
    smash360_command_trace=true;
    unsigned chosen=0;
    for(unsigned i=0;i<32768;++i) {
        SmashCommandTrace trace;
        if(trace.active) ++chosen;
        clockValue+=2;
        trace.Mark(SMASH_CMD_FETCH);
        clockValue+=3;
        trace.Mark(SMASH_CMD_BOUNDS);
        clockValue+=5;
        trace.Opcode(0xDE);
        trace.Mark(SMASH_CMD_TRACE);
        clockValue+=7;
        trace.Mark(SMASH_CMD_DISPATCH);
        clockValue+=11;
    }
    assert(chosen>160 && chosen<360);
    assert(smash360_command_samples.calls==32768);
    assert(smash360_command_samples.sampled==chosen);
    assert(smash360_command_samples.ticks[SMASH_CMD_LOOP]==chosen*2);
    assert(smash360_command_samples.ticks[SMASH_CMD_FETCH]==chosen*3);
    assert(smash360_command_samples.ticks[SMASH_CMD_BOUNDS]==chosen*5);
    assert(smash360_command_samples.ticks[SMASH_CMD_TRACE]==chosen*7);
    assert(smash360_command_samples.ticks[SMASH_CMD_DISPATCH]==chosen*11);
    assert(smash360_command_samples.opcodeTicks[0xDE]==chosen*11);
    assert(smash360_command_samples.opcodeSamples[0xDE]==chosen);
    unsigned before=smash360_command_samples.sampled;
    while(smash360_command_samples.sampled==before) {
        clockValue=0xfffffffeu;
        SmashCommandTrace early;
        clockValue=3;
    }
    assert(smash360_command_samples.ticks[SMASH_CMD_LOOP]==chosen*2+5);
    assert(smash360_command_samples.opcodeSamples[0xDE]==chosen);
    {
        clockValue=0xfffffffeu;
        SmashWalkTrace walk;
        clockValue=3;walk.Mark(SMASH_WALK_EXECUTE);
        clockValue=13;walk.Mark(SMASH_WALK_FINISH);
        clockValue=20;
    }
    assert(smash360_command_samples.walkTicks[SMASH_WALK_SETUP]==5);
    assert(smash360_command_samples.walkTicks[SMASH_WALK_EXECUTE]==10);
    assert(smash360_command_samples.walkTicks[SMASH_WALK_FINISH]==7);
    assert(smash360_command_samples.walks==1);
    puts("command sampler: disabled, selection, phases, opcode attribution, early return, wrap, whole-walk accounting passed");
}
