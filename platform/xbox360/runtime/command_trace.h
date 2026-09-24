#pragma once
#include "perf_trace.h"
// Same SoH-derived low-word time base as the triangle sampler. One random
// command in 128 is timed; all commands and their original handlers execute.
enum SmashCommandPhase { SMASH_CMD_LOOP, SMASH_CMD_FETCH, SMASH_CMD_BOUNDS,
    SMASH_CMD_TRACE, SMASH_CMD_DISPATCH, SMASH_CMD_PHASES };
enum SmashWalkPhase { SMASH_WALK_SETUP, SMASH_WALK_EXECUTE, SMASH_WALK_FINISH, SMASH_WALK_PHASES };
struct SmashCommandSamples {
    uint64_t ticks[SMASH_CMD_PHASES], opcodeTicks[256], walkTicks[SMASH_WALK_PHASES];
    unsigned opcodeSamples[256], calls, sampled, walks;
};
extern bool smash360_command_trace;
extern __declspec(thread) SmashCommandSamples smash360_command_samples;
extern __declspec(thread) uint32_t smash360_command_random;
struct SmashCommandTrace {
    bool active;
    unsigned phase, opcode;
    uint32_t start;
    __forceinline SmashCommandTrace() : active(false) {
        if(!smash360_command_trace)return;
        ++smash360_command_samples.calls;
        uint32_t x=smash360_command_random;
        x^=x<<13;x^=x>>17;x^=x<<5;smash360_command_random=x;
        active=(x&127)==0;
        if(active) {
            ++smash360_command_samples.sampled;
            phase=SMASH_CMD_LOOP;opcode=256;start=Smash360_PerfCounter();
        }
    }
    __forceinline void Opcode(uint8_t value) { if(active)opcode=value; }
    __forceinline void Mark(unsigned next) {
        if(!active)return;
        const uint32_t now=Smash360_PerfCounter();
        const uint32_t elapsed=now-start;
        smash360_command_samples.ticks[phase]+=elapsed;
        if(phase==SMASH_CMD_DISPATCH && opcode<256) {
            smash360_command_samples.opcodeTicks[opcode]+=elapsed;
            ++smash360_command_samples.opcodeSamples[opcode];
        }
        phase=next;start=now;
    }
    __forceinline ~SmashCommandTrace() { if(active)Mark(phase); }
private:
    SmashCommandTrace(const SmashCommandTrace&);
    SmashCommandTrace& operator=(const SmashCommandTrace&);
};
// A few reads per Run split actual total time into setup, command walk, and
// final flush/composition. These totals are measured, not extrapolated.
struct SmashWalkTrace {
    bool active;
    unsigned phase;
    uint32_t start;
    __forceinline SmashWalkTrace() : active(smash360_command_trace) {
        if(active) { ++smash360_command_samples.walks;phase=SMASH_WALK_SETUP;start=Smash360_PerfCounter(); }
    }
    __forceinline void Mark(unsigned next) {
        if(!active)return;
        const uint32_t now=Smash360_PerfCounter();
        smash360_command_samples.walkTicks[phase]+=uint32_t(now-start);
        phase=next;start=now;
    }
    __forceinline ~SmashWalkTrace() { if(active)Mark(phase); }
private:
    SmashWalkTrace(const SmashWalkTrace&);
    SmashWalkTrace& operator=(const SmashWalkTrace&);
};
void Smash360_ReportCommandTrace(unsigned frames);
