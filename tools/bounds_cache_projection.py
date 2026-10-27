"""Cache proven UNKNOWN gaps in pinned BattleShip's existing DL range checker.

Compose after profiling, before XDK syntax lowering. The original locked scan,
positive cache and synchronization remain authoritative. Every anchor is exact.
"""
import re
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


SPAN = '''
// A span [base, end) around addr whose every address shares its answer until
// the registry changes, for walkers that advance inside one display list: a
// current-generation ring entry that holds addr (IN_RANGE), or the proven
// unknown gap holding it (UNKNOWN). Walked-past answers report no span.
extern "C" int port_dl_check_addr_span(uintptr_t addr, uintptr_t* base, uintptr_t* end) {
    const int result = port_dl_check_addr(addr);
    *base = *end = 0;
    const uint64_t gen = sRangesGen.load(std::memory_order_acquire);
    if (result == PORT_DL_UNKNOWN) {
        const UnknownCache& u = sUnknownCache;
        if (u.valid && u.gen == gen && addr >= u.gap.lo && addr <= u.gap.hi) {
            *base = u.gap.lo;
            // An inclusive gap ending at the top of memory loses only that byte.
            *end = u.gap.hi == ~uintptr_t(0) ? u.gap.hi : u.gap.hi + 1;
        }
        return result;
    }
    if (result != PORT_DL_IN_RANGE) return result;
    for (unsigned i = 0; i < kHitCacheEntries; ++i) {
        const HitCache& c = sHitCache[i];
        if (c.gen == gen && c.size != 0 && addr - c.base < c.size) {
            *base = c.base;
            *end = c.base + c.size;
            break;
        }
    }
    return result;
}
'''


def span(text):
    """Append the span query after the checker; compose after transform()."""
    return text.rstrip('\n') + '\n' + SPAN


WALKED_PAST = '''// Commands advance inside one display list, so most never need the checker:
// the span of its last answer covers them and holds no walked-past address.
// G_DL checks its target, then runs its translated copy and returns to its
// caller: a few recent spans keep all of those off the checker. Each Run
// starts empty; a registry change during a Run is already a use-after-free
// race.
extern "C" int port_dl_check_addr_span(uintptr_t addr, uintptr_t* base, uintptr_t* end);
static uintptr_t sXboxWalkSpans[4][2] = { { 0, 0 } };
static __declspec(noinline) bool XboxWalkedPastMiss(uintptr_t addr) {
    memmove(sXboxWalkSpans[1], sXboxWalkSpans[0], 3 * sizeof(sXboxWalkSpans[0]));
    return port_dl_check_addr_span(addr, &sXboxWalkSpans[0][0], &sXboxWalkSpans[0][1]) == kDLBoundsWalkedPast;
}
static __forceinline bool XboxWalkedPast(uintptr_t addr) {
    for (unsigned i = 0; i < 4; ++i)
        if (addr - sXboxWalkSpans[i][0] < sXboxWalkSpans[i][1] - sXboxWalkSpans[i][0]) return false;
    return XboxWalkedPastMiss(addr);
}
'''


def interpreter(text):
    """Route the walk and G_DL target checks through the span cache above."""
    walked = re.compile(r'static (?:constexpr|const) int kDLBoundsWalkedPast = 2;\n')
    if len(walked.findall(text)) != 1:
        raise ValueError('Walked-past constant anchor changed')
    text = walked.sub(lambda m: m.group(0) + WALKED_PAST, text, 1)
    for address in ('(uintptr_t)cmd', '(uintptr_t)(cmd + 1)', 'subAddr'):
        text = once(text, 'sDLBoundsCheck && sDLBoundsCheck(%s) == kDLBoundsWalkedPast' % address,
                    'sDLBoundsCheck && XboxWalkedPast(%s)' % address)
    run = re.compile(r'\n    sXboxTriangleRunEnabled = [^\n]*;\n')
    if len(run.findall(text)) != 1:
        raise ValueError('Triangle run start anchor changed')
    return run.sub(lambda m: m.group(0) + '    memset(sXboxWalkSpans, 0, sizeof(sXboxWalkSpans));\n', text, 1)
