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
''' % (LOOKUPS, ', '.join(['{ 0, 0, 0, false }'] * LOOKUPS)))
    text = once(text, '\t\tsPortRelocFileRanges.end());\n', '\t\tsPortRelocFileRanges.end());\n\t++gPortRelocFileRangesGen;\n')
    text = once(text, '\tsPortRelocFileRanges.clear();\n', '\tsPortRelocFileRanges.clear();\n\t++gPortRelocFileRangesGen;\n')
    push = re.compile(r'(sPortRelocFileRanges\.push_back\(\{.*?\}\);)', re.S)
    if len(push.findall(text)) != 2:
        raise ValueError('Reloc file range push_back anchors changed')
    text = push.sub(r'\1\n\t++gPortRelocFileRangesGen;', text)
    signature = 'bool portRelocFindContainingFile(const void *ptr, uintptr_t *out_base, size_t *out_size)\n{'
    return once(text, signature, '''\
static bool portRelocFirstContainingFile(const void *ptr, uintptr_t *out_base, size_t *out_size);
// Holds the reloc lock (overlap projection): fills one entry from the live ranges.
static void portRelocScanContainingFile(uintptr_t addr, PortRelocLookup &entry)
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
		portRelocScanContainingFile(addr, *last);
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
    """RelocPointerTable.cpp: a generation every slot mutation bumps."""
    text = once(text, '/* Index 0 reserved. */\n',
                '/* Index 0 reserved. */\nextern "C" volatile unsigned gPortRelocPointerTableGen = 1;\n')
    text = once(text, '    sSlots[index].ptr = ptr;\n    return makeToken(index, gen);',
                '    sSlots[index].ptr = ptr;\n    ++gPortRelocPointerTableGen;\n    return makeToken(index, gen);')
    text = once(text, '            sFreeIndices.push_back(i);\n',
                '            sFreeIndices.push_back(i);\n            ++gPortRelocPointerTableGen;\n')
    return once(text, '    sNextIndex = 1;\n    sFreeIndices.clear();\n',
                '    sNextIndex = 1;\n    sFreeIndices.clear();\n    ++gPortRelocPointerTableGen;\n')


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
    Fast::F3DGfx* result = XboxNormalizeDisplayListPointerSlow(dlist);
    entry.source = dlist; entry.result = result;
    entry.packed = sXboxPackedListGen; entry.ranges = ranges;
    return result;
}
static Fast::F3DGfx* XboxNormalizeDisplayListPointerSlow(Fast::F3DGfx* dlist) {'''

RESOLVE = '''// SegAddr offers every 32-bit word to the token table; answers are fixed until
// a slot changes. Only the walking thread resolves here, one Run at a time.
extern "C" volatile unsigned gPortRelocPointerTableGen;
struct XboxResolvedToken { uint32_t token; void* ptr; unsigned gen; };
static XboxResolvedToken sXboxResolvedTokens[1024];
static __forceinline void* XboxTryResolvePointer(uint32_t token) {
    XboxResolvedToken& entry = sXboxResolvedTokens[(token ^ (token >> 10) ^ (token >> 20)) & 1023];
    const unsigned gen = gPortRelocPointerTableGen;
    if (entry.gen != gen || entry.token != token) {
        entry.ptr = portRelocTryResolvePointer(token);
        entry.token = token;
        entry.gen = gen;
    }
    return entry.ptr;
}
'''


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
