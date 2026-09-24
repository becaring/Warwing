"""Cache proven UNKNOWN gaps in pinned BattleShip's existing DL range checker.

Compose after profiling, before XDK syntax lowering. The original locked scan,
positive cache and synchronization remain authoritative. Every anchor is exact.
"""
from profile_projections import once


def transform(text):
    text = '#include "memory/address_gap.h"\n' + text
    # This cache belongs exclusively to the calling thread and is not written
    # during the hit predicate. XDK otherwise copies it through stack memory
    # for every command (ld/std followed immediately by dependent reloads).
    text = once(text, '        const HitCache c = sHitCache;',
                '        const HitCache& c = sHitCache;')
    text = once(text, 'thread_local HitCache sHitCache;', '''thread_local HitCache sHitCache;
struct UnknownCache {
    uint64_t gen;
    Shipyard::Memory::AddressGap gap;
    bool valid;
};
thread_local UnknownCache sUnknownCache = {0, {0, 0}, false};''')
    text = once(text, '    Smash360_PerfDetailCount(SMASH_COUNT_BOUNDS_MISS);', '''    // Registry changes invalidate unknown gaps exactly like positive hits.
    if (sUnknownCache.valid && sUnknownCache.gen == gen &&
        addr >= sUnknownCache.gap.lo && addr <= sUnknownCache.gap.hi) {
        Smash360_PerfDetailCount(SMASH_COUNT_BOUNDS_HIT);
        Smash360_PerfDetailCount(SMASH_COUNT_BOUNDS_UNKNOWN_HIT);
        return PORT_DL_UNKNOWN;
    }
    Smash360_PerfDetailCount(SMASH_COUNT_BOUNDS_MISS);''')
    text = once(text, '    bool walked_past = false;', '''    Shipyard::Memory::AddressGap unknownGap = {0, ~uintptr_t(0)};
    bool walked_past = false;''')
    text = once(text, '        Smash360_PerfDetailCount(SMASH_COUNT_BOUNDS_VISITS);', '''        Smash360_PerfDetailCount(SMASH_COUNT_BOUNDS_VISITS);
        unknownGap.Exclude(addr, e.base, e.size);
        // Preserve the original unsigned wrapped endpoint for walked-past.
        unknownGap.Exclude(addr, uintptr_t(e.base + e.size), kWalkPastWindow);''')
    text = once(text, '    Smash360_PerfDetailCount(walked_past ? SMASH_COUNT_BOUNDS_PAST : SMASH_COUNT_BOUNDS_UNKNOWN);', '''    if (!walked_past) {
        sUnknownCache.gen = gen;
        sUnknownCache.gap = unknownGap;
        sUnknownCache.valid = true;
    }
    Smash360_PerfDetailCount(walked_past ? SMASH_COUNT_BOUNDS_PAST : SMASH_COUNT_BOUNDS_UNKNOWN);''')
    # XDK otherwise saves nine nonvolatile registers and allocates a scan
    # frame even on every cached hit. Isolate the unchanged locking/scan body
    # as a cold function, like SoH's noinline material rebuilds. Generation
    # acquisition, classification, overlapping ranges and invalidation stay
    # in the same order; the miss receives the exact snapshot just acquired.
    signature = 'extern "C" int port_dl_check_addr(uintptr_t addr) {'
    start = text.index(signature)
    cold_start = text.index('    Smash360_PerfDetailCount(SMASH_COUNT_BOUNDS_MISS);', start)
    cold_end = text.index('\n}\n', cold_start)
    cold_body = text[cold_start:cold_end]
    text = text[:cold_start] + '    return XboxCheckDLBoundsMiss(addr, gen);' + text[cold_end:]
    helper = 'static __declspec(noinline) int XboxCheckDLBoundsMiss(uintptr_t addr, uint64_t gen) {\n' + cold_body + '\n}\n\n'
    text = once(text, signature, helper + signature)
    return text
