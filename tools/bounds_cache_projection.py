"""Cache proven UNKNOWN gaps in pinned BattleShip's existing DL range checker.

Compose after profiling, before XDK syntax lowering. The original locked scan,
positive cache and synchronization remain authoritative. Every anchor is exact.
"""
from profile_projections import once


def transform(text):
    text = '#include "memory/address_gap.h"\n' + text
    # G_DL calls and returns alternate between files, so one entry per recent
    # range keeps them off the locked scan. Entries are read in place: XDK
    # otherwise copies each through stack memory (ld/std, dependent reloads).
    text = once(text, '    {\n        const HitCache c = sHitCache;', '''\
    for (unsigned i = 0; i < kHitCacheEntries; ++i) {
        const HitCache& c = sHitCache[i];''')
    text = once(text, '            sHitCache = HitCache{gen, e.base, e.size};',
                '            sHitCache[sHitCacheNext++ % kHitCacheEntries] = HitCache{gen, e.base, e.size};')
    text = once(text, 'thread_local HitCache sHitCache;', '''const unsigned kHitCacheEntries = 8;
thread_local HitCache sHitCache[kHitCacheEntries];
thread_local unsigned sHitCacheNext = 0;
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
    scan_end = '        }\n    }\n    Smash360_PerfDetailCount(walked_past'
    text = once(text, scan_end, '''        }
        // Only UNKNOWN results publish a gap. Keep scanning for overlapping hits.
        if (!walked_past) {
            unknownGap.Exclude(addr, e.base, e.size);
            // Preserve the original unsigned wrapped endpoint for walked-past.
            unknownGap.Exclude(addr, uintptr_t(e.base + e.size), kWalkPastWindow);
        }
    }
    Smash360_PerfDetailCount(walked_past''')
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
