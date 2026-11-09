"""Answer repeated reloc lookups from per-thread memos instead of locked scans.

The display-list walk asks the reloc layer three things per command family:
SegAddr resolves every 32-bit word as a possible pointer token, G_DL and
normalization ask which loaded file contains an address, and normalization
then hashes the callee into the packed-list map. Each ask takes the overlap
reloc lock, and file lookups scan every loaded file. Answers are fixed until
the state behind them changes, so each memo is validated by a generation that
every mutation bumps. A memo hit takes no lock; a hit read during a concurrent
mutation is the answer from just before it, as a lookup that won the lock
first would have seen. Mutating loads also fence the replay, so only
animation loads, which display lists never read, run concurrently.

File ranges are disjoint (every insert evicts overlaps first), so a cached
containing range is exact, and a miss proves the whole gap between its
neighbouring files.
"""
import re
from profile_projections import once

LOOKUPS = 4


def transform(text):
    """lbreloc_bridge.cpp: file-range generation and the per-thread lookup cache."""
    # Every mutation below bumps the generation; re-audit if new ones appear.
    operations = set(re.findall(r'\bsPortRelocFileRanges\.(\w+)\s*\(', text))
    if operations != {'erase', 'begin', 'end', 'push_back', 'clear'}:
        raise ValueError('Re-audit reloc file range mutations: ' + str(operations))
    text = once(text, 'static std::vector<PortRelocFileRange> sPortRelocFileRanges;\n', '''\
static std::vector<PortRelocFileRange> sPortRelocFileRanges;
extern "C" volatile unsigned gPortRelocFileRangesGen = 1;
// A found file is [base, base + size); a miss holds the proven gap [base, base + size].
struct PortRelocLookup { unsigned gen; uintptr_t base; size_t size; bool found; };
static __declspec(thread) PortRelocLookup sPortRelocLookups[%d] = { %s };
static __declspec(thread) unsigned sPortRelocLookupNext = 0;
// Writers hold the reloc lock; an odd sequence marks a mutation in progress. The reserve keeps
// the storage in place, so an unlocked reader never follows a freed buffer.
extern "C" volatile unsigned gPortRelocRangesSeq = 0;
#ifdef _XBOX
#define PORT_RANGES_ORDER() __lwsync()
#else
#define PORT_RANGES_ORDER() ((void)0)
#endif
#define PORT_RANGES_BEGIN() (++gPortRelocRangesSeq, PORT_RANGES_ORDER())
#define PORT_RANGES_END() (PORT_RANGES_ORDER(), ++gPortRelocRangesSeq)
static const size_t kPortRelocRangesReserve = 4096;
''' % (LOOKUPS, ', '.join(['{ 0, 0, 0, false }'] * LOOKUPS)))
    text = once(text, '\tsPortRelocFileRanges.erase(\n', '\tPORT_RANGES_BEGIN();\n\tsPortRelocFileRanges.erase(\n')
    text = once(text, '\t\tsPortRelocFileRanges.end());\n',
                '\t\tsPortRelocFileRanges.end());\n\tPORT_RANGES_END();\n\t++gPortRelocFileRangesGen;\n')
    text = once(text, '\tsPortRelocFileRanges.clear();\n',
                '\tPORT_RANGES_BEGIN();\n\tsPortRelocFileRanges.clear();\n\tPORT_RANGES_END();\n\t++gPortRelocFileRangesGen;\n')
    push = re.compile(r'(sPortRelocFileRanges\.push_back\(\{.*?\}\);)', re.S)
    if len(push.findall(text)) != 2:
        raise ValueError('Reloc file range push_back anchors changed')
    text = push.sub(r'PORT_RANGES_BEGIN();\n\tif (sPortRelocFileRanges.capacity() < kPortRelocRangesReserve)'
                    r' sPortRelocFileRanges.reserve(kPortRelocRangesReserve);\n'
                    r'\t\1\n\tPORT_RANGES_END();\n\t++gPortRelocFileRangesGen;', text)
    signature = 'bool portRelocFindContainingFile(const void *ptr, uintptr_t *out_base, size_t *out_size)\n{'
    return once(text, signature, '''\
static bool portRelocFirstContainingFile(const void *ptr, uintptr_t *out_base, size_t *out_size);
// Fills one entry from the live ranges; callers hold the lock or check the sequence.
static void portRelocScanRanges(uintptr_t addr, PortRelocLookup &entry)
{
	entry.found = portRelocFirstContainingFile(reinterpret_cast<const void *>(addr), &entry.base, &entry.size);
	if (entry.found)
	{
		return;
	}
	uintptr_t lo = 0, hi = ~uintptr_t(0);
	for (const auto &range : sPortRelocFileRanges)
	{
		if (range.size == 0)
		{
			continue;
		}
		if (range.base > addr)
		{
			if (range.base - 1 < hi)
			{
				hi = range.base - 1;
			}
		}
		else if (range.base + range.size > lo)
		{
			lo = range.base + range.size;
		}
	}
	entry.base = lo;
	entry.size = hi - lo;
}

// Holds the reloc lock (overlap projection).
static void portRelocScanContainingFile(uintptr_t addr, PortRelocLookup &entry)
{
	portRelocScanRanges(addr, entry);
}

// Render lookups skip the lock that animation loads hold for milliseconds; a scan that
// overlapped a mutation reports failure and the caller rescans under the lock.
static bool portRelocScanContainingFileUnlocked(uintptr_t addr, PortRelocLookup &entry)
{
	const unsigned seq = gPortRelocRangesSeq;
	if (seq & 1)
	{
		return false;
	}
	PORT_RANGES_ORDER();
	portRelocScanRanges(addr, entry);
	PORT_RANGES_ORDER();
	return gPortRelocRangesSeq == seq;
}

bool portRelocFindContainingFile(const void *ptr, uintptr_t *out_base, size_t *out_size)
{
	const uintptr_t addr = reinterpret_cast<uintptr_t>(ptr);
	const unsigned gen = gPortRelocFileRangesGen;
	PortRelocLookup *last = NULL;
	for (unsigned i = 0; i < %d; ++i)
	{
		PortRelocLookup &entry = sPortRelocLookups[i];
		if (entry.gen == gen && (entry.found ? addr - entry.base < entry.size : addr - entry.base <= entry.size))
		{
			last = &entry;
			break;
		}
	}
	if (last == NULL)
	{
		last = &sPortRelocLookups[sPortRelocLookupNext++ %% %d];
		if (!portRelocScanContainingFileUnlocked(addr, *last))
		{
			portRelocScanContainingFile(addr, *last);
		}
		last->gen = gen;
	}
	if (!last->found)
	{
		return FALSE;
	}
	if (out_base != NULL)
	{
		*out_base = last->base;
	}
	if (out_size != NULL)
	{
		*out_size = last->size;
	}
	return TRUE;
}

static bool portRelocFirstContainingFile(const void *ptr, uintptr_t *out_base, size_t *out_size)
{''' % (LOOKUPS, LOOKUPS))


def pointer_table(text):
    """RelocPointerTable.cpp: one generation for freed slots and one for registrations."""
    text = once(text, '/* Index 0 reserved. */\n',
                '/* Index 0 reserved. */\nextern "C" volatile unsigned gPortRelocPointerTableGen = 1;\n'
                'extern "C" volatile unsigned gPortRelocPointerTableAddGen = 1;\n' + GROWTH)
    text = once(text, '    sSlots[index].ptr = ptr;\n    return makeToken(index, gen);',
                '    sSlots[index].ptr = ptr;\n    ++gPortRelocPointerTableAddGen;\n    return makeToken(index, gen);')
    text = once(text, '            sFreeIndices.push_back(i);\n',
                '            sFreeIndices.push_back(i);\n            ++gPortRelocPointerTableGen;\n')
    text = once(text, '    sNextIndex = 1;\n    sFreeIndices.clear();\n',
                '    sNextIndex = 1;\n    sFreeIndices.clear();\n    ++gPortRelocPointerTableGen;\n')
    # Growth keeps the old array: an unlocked reader may still be reading it.
    text = once(text, '        Slot *grown = (Slot *)realloc(sSlots, newCapacity * sizeof(Slot));\n',
                '        ++gPortRelocSlotGrowth;\n        PORT_RELOC_ORDER();\n'
                '        Slot *grown = (Slot *)malloc(newCapacity * sizeof(Slot));\n'
                '        if (grown != nullptr) memcpy(grown, sSlots, sCapacity * sizeof(Slot));\n')
    text = once(text, '        sCapacity = newCapacity;\n',
                '        sCapacity = newCapacity;\n        PORT_RELOC_ORDER();\n        ++gPortRelocSlotGrowth;\n')
    anchor = 'void *portRelocTryResolvePointer(uint32_t token)\n{'
    return once(text, anchor, UNLOCKED + anchor)


GROWTH = '''#ifdef _XBOX
#define PORT_RELOC_ORDER() __lwsync()
#else
#define PORT_RELOC_ORDER() ((void)0)
#endif
// Odd while the slot array is being replaced.
static volatile unsigned gPortRelocSlotGrowth = 0;
'''
UNLOCKED = '''/* Lock-free resolve for render lookups. A slot's pointer is fixed while its
 * generation matches the token's: invalidation bumps the generation before a
 * slot is reused. Reading the generation on both sides of the pointer rejects
 * a concurrent reuse; a concurrent growth falls back to the locked lookup. */
void *portRelocTryResolvePointerUnlocked(uint32_t token)
{
    const unsigned growth = gPortRelocSlotGrowth;
    const uint32_t index = token & TOKEN_INDEX_MASK;
    const uint32_t tokenGen = token >> TOKEN_GENERATION_SHIFT;
    if (growth & 1) {
        return portRelocTryResolvePointer(token);
    }
    PORT_RELOC_ORDER();
    // Volatile: the second generation read must not reuse the first.
    const volatile Slot *slots = sSlots;
    if (token == 0 || tokenGen == 0 || index == 0 || slots == nullptr || index >= sNextIndex ||
        slots[index].gen != tokenGen) {
        return nullptr;
    }
    void *ptr = slots[index].ptr;
    PORT_RELOC_ORDER();
    if (slots[index].gen != tokenGen || gPortRelocSlotGrowth != growth) {
        return portRelocTryResolvePointer(token);
    }
    return ptr;
}

'''


NORMALIZE = 'Fast::F3DGfx* portNormalizeDisplayListPointer(Fast::F3DGfx* dlist) {'
MEMO = '''// The packed-list map and the reloc file ranges determine each answer. Only
// the walking thread normalizes, one Run at a time.
static unsigned sXboxPackedListGen = 1;
struct XboxNormalizedList { const void* source; Fast::F3DGfx* result; unsigned packed, ranges; };
static XboxNormalizedList sXboxNormalizedLists[1024];
static Fast::F3DGfx* XboxNormalizeDisplayListPointerSlow(Fast::F3DGfx* dlist);
Fast::F3DGfx* portNormalizeDisplayListPointer(Fast::F3DGfx* dlist) {
    const uintptr_t key = (uintptr_t)dlist;
    XboxNormalizedList& entry = sXboxNormalizedLists[((key >> 3) ^ (key >> 13)) & 1023];
    const unsigned ranges = gPortRelocFileRangesGen;
    if (entry.source == dlist && entry.packed == sXboxPackedListGen && entry.ranges == ranges && dlist)
        return entry.result;
    Smash360_PerfDetailCount(SMASH_COUNT_NORMALIZE_MISS);
    Fast::F3DGfx* result = XboxNormalizeDisplayListPointerSlow(dlist);
    entry.source = dlist; entry.result = result;
    entry.packed = sXboxPackedListGen; entry.ranges = ranges;
    return result;
}
static Fast::F3DGfx* XboxNormalizeDisplayListPointerSlow(Fast::F3DGfx* dlist) {'''

RESOLVE = '''// SegAddr offers every 32-bit word to the token table. A resolved pointer holds
// until a slot is freed; registering can only turn a "no token" answer into one,
// so loads on the game worker no longer flush resolved answers. Both generations are read before the
// lookup, so a concurrent change leaves a stale entry that the next lookup refreshes.
extern "C" volatile unsigned gPortRelocPointerTableGen, gPortRelocPointerTableAddGen;
// A miss reads the table without the reloc lock, which game-worker loads hold for milliseconds.
extern "C" void* portRelocTryResolvePointerUnlocked(uint32_t token);
struct XboxResolvedToken { uint32_t token; void* ptr; unsigned gen, added; };
static XboxResolvedToken sXboxResolvedTokens[1024];
static __forceinline void* XboxTryResolvePointer(uint32_t token) {
    XboxResolvedToken& entry = sXboxResolvedTokens[(token ^ (token >> 10) ^ (token >> 20)) & 1023];
    const unsigned gen = gPortRelocPointerTableGen;
    const unsigned added = gPortRelocPointerTableAddGen;
    if (entry.gen != gen || entry.token != token || (!entry.ptr && entry.added != added)) {
        Smash360_PerfDetailCount(SMASH_COUNT_TOKEN_MISS);
        entry.ptr = portRelocTryResolvePointerUnlocked(token);
        entry.token = token;
        entry.gen = gen;
        entry.added = added;
    }
    return entry.ptr;
}
'''


FIXUP_SETS = ("sStructU16Fixups", "sTexFixupWords", "sDeswizzle4cFixups", "sChainSlotAddrs")


def fixup_sets(text):
    """lbreloc_byteswap.cpp: every load evicts its range from the fixup and chain-slot sets
    while holding the reloc lock render lookups need. Hash sets made that a walk over every
    address recorded for every loaded file; ordered sets erase only the range."""
    for name in FIXUP_SETS:
        text = once(text, "static std::unordered_set<uintptr_t> " + name + ";", "static std::set<uintptr_t> " + name + ";")
    text = once(text, "static std::unordered_map<uintptr_t, unsigned int> sTexFixupExtent;",
                "static std::map<uintptr_t, unsigned int> sTexFixupExtent;")
    text = once(text, "#include <unordered_set>\n", "#include <unordered_set>\n#include <map>\n#include <set>\n")
    text = once(text, '''\
\tauto evict_set = [&](std::unordered_set<uintptr_t> &s) {
\t\tfor (auto it = s.begin(); it != s.end(); ) {
\t\t\tif (*it >= lo && *it < hi) it = s.erase(it);
\t\t\telse ++it;
\t\t}
\t};''', '''\
\tauto evict_set = [&](std::set<uintptr_t> &s) { s.erase(s.lower_bound(lo), s.lower_bound(hi)); };''')
    return once(text, '''\
\tfor (auto it = sTexFixupExtent.begin(); it != sTexFixupExtent.end(); ) {
\t\tif (it->first >= lo && it->first < hi) it = sTexFixupExtent.erase(it);
\t\telse ++it;
\t}''', '''\
\tsTexFixupExtent.erase(sTexFixupExtent.lower_bound(lo), sTexFixupExtent.lower_bound(hi));''')


def interpreter(text):
    """Memoize normalization and SegAddr token resolves; apply before XDK lowering."""
    operations = set(re.findall(r'\bsPortPackedDisplayListCache\.(\w+)\s*\(', text))
    if not operations <= {'find', 'end', 'emplace', 'insert', 'clear', 'begin', 'erase'}:
        raise ValueError('Re-audit packed display-list map mutations: ' + str(operations))
    # File scope: C language linkage does not reach into the unnamed namespace.
    packed = re.compile(r'namespace \{\n\n(?=(?:constexpr|const) size_t PORT_PACKED_GFX_SIZE)')
    if len(packed.findall(text)) != 1:
        raise ValueError('Packed display-list namespace anchor changed')
    text = packed.sub('extern "C" volatile unsigned gPortRelocFileRangesGen;\nnamespace {\n\n', text, 1)
    text = once(text, NORMALIZE, MEMO)
    text = once(text, '    sPortPackedDisplayListCache.clear();\n',
                '    sPortPackedDisplayListCache.clear();\n    ++sXboxPackedListGen;\n')
    text = once(text, '            it = sPortPackedDisplayListCache.erase(it);\n',
                '            it = sPortPackedDisplayListCache.erase(it);\n            ++sXboxPackedListGen;\n')
    text = once(text, 'void* Interpreter::SegAddr(uintptr_t w1) {', RESOLVE + 'void* Interpreter::SegAddr(uintptr_t w1) {')
    return once(text, 'void* relocPtr = portRelocTryResolvePointer((uint32_t)w1);',
                'void* relocPtr = XboxTryResolvePointer((uint32_t)w1);')
