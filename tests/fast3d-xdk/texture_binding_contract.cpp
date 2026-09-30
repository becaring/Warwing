#include "fast/interpreter.h"
#include "fast3d/texture_bindings.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <algorithm>
using namespace Fast;
#define SPDLOG_WARN(...) ((void)0)
#undef TEXTURE_CACHE_MAX_SIZE
static const size_t TEXTURE_CACHE_MAX_SIZE = 8;
static unsigned hashCalls;
static bool verifyContent = true;
static bool PortTextureCacheVerifyEnabled() { return verifyContent; }
// REAL_HASH
static void Require(bool value, const char *message) {
    if (!value) {
        std::fprintf(stderr, "FAIL %s\n", message);
        std::exit(1);
    }
}
struct Image {
    uint64_t contents;
    unsigned sampler;
    Image() : contents(0), sampler(0) {}
};
struct Draw {
    uint64_t contents[6];
    unsigned sampler[6], shader;
};
struct Backend {
    unsigned selected[6], next, selects, uploads, drawCalls, shader;
    unsigned nativeSampler[6];
    unsigned uploadSlot;
    std::map<unsigned, Image> images;
    std::vector<Draw> output;
    Backend() : next(1), selects(0), uploads(0), drawCalls(0), shader(0), uploadSlot(0) {
        std::memset(selected, 0, sizeof(selected));
        std::memset(nativeSampler, 0, sizeof(nativeSampler));
    }
    unsigned NewTexture() { return next++; }
    void SelectTexture(int slot, unsigned id) {
        selected[slot] = id;
        uploadSlot = slot;
        nativeSampler[slot] = images[id].sampler;
        ++selects;
    }
    void SelectTextureFb(unsigned id) {
        selected[0] = 1000 + id;
        images[1000 + id].contents = 0xfb0000 + id;
        nativeSampler[0] = images[1000 + id].sampler;
    }
    void SetSamplerParameters(int slot, bool linear, unsigned s, unsigned t) {
        nativeSampler[slot] = images[selected[slot]].sampler = linear | (s << 1) | (t << 5);
    }
    void Upload(uint64_t content) {
        images[selected[uploadSlot]].contents = content;
        ++uploads;
    }
    void Submit(unsigned count) {
        if (!count)
            return;
        ++drawCalls;
        Draw draw = {};
        draw.shader = shader;
        for (unsigned slot = 0; slot < 6; ++slot) {
            draw.contents[slot] = images[selected[slot]].contents;
            draw.sampler[slot] = nativeSampler[slot];
        }
        for (unsigned i = 0; i < count; ++i)
            output.push_back(draw);
    }
};
struct MiniRdp {
    bool textures_changed[2];
    struct Loaded {
        bool masked, blended;
    } loaded_texture[2];
    MiniRdp() { std::memset(this, 0, sizeof(*this)); }
};
struct Combiner {
    int *prg[16];
    uint64_t shader_id0, shader_id1;
    Combiner() { std::memset(this, 0, sizeof(*this)); }
};
// ENGINE_BEGIN
struct ENGINE {
    Backend backend;
    Backend *mRapi;
    GfxTextureCache mTextureCache;
    RenderingState mRenderingState;
    Shipyard::Fast3D::TextureBindings<SHADER_MAX_TEXTURES> mXboxTextureBindings;
    MiniRdp rdp;
    MiniRdp *mRdp;
    TextureCacheKey requests[6];
    Combiner combiner;
    int programs[16];
    bool failShader;
    unsigned pending, imports, masks;
    ENGINE() : mRapi(&backend), mRenderingState(), mRdp(&rdp), failShader(false), pending(0), imports(0), masks(0) {
        std::memset(requests, 0, sizeof(requests));
        mTextureCache.map.reserve(TEXTURE_CACHE_MAX_SIZE);
        for (unsigned i = 0; i < 16; ++i)
            programs[i] = i + 1;
    }
    void Flush() {
        backend.Submit(pending);
        pending = 0;
    }
    void Queue() { ++pending; }
    void XboxInvalidateTextureBindings();
    bool TextureCacheLookup(int i, const TextureCacheKey &key);
    void TextureCacheClear();
    void TextureCacheDelete(const uint8_t *origAddr);
    void TextureCacheDeleteRange(const uint8_t *base, size_t size);
    Backend *GetCurrentRenderingAPI();
    void ImportGroup();
    void Shader(unsigned tm);
    int *LookupOrCreateShaderProgram(uint64_t a, uint64_t b) {
        if (failShader) {
            backend.shader = 0;
            return NULL;
        }
        unsigned tm = (unsigned)(b / SHADER_OPT(TEXEL0_CLAMP_S));
        backend.shader = tm + 1;
        return &programs[tm];
    }
    void ImportTexture(int i, int, bool) {
        ++imports;
        if (!TextureCacheLookup(i, requests[i]))
            backend.Upload(requests[i].size_bytes
                               ? PortTextureContentHash(requests[i].texture_addr, requests[i].size_bytes)
                               : 0xabcdef);
    }
    void ImportTextureMask(int i, int tile) {
        ++masks;
        ImportTexture(i, tile, false);
    }
    void AllImports() {
        rdp.textures_changed[0] = rdp.textures_changed[1] = true;
        ImportGroup();
    }
    void Sampler(unsigned slot, bool linear, unsigned s, unsigned t) {
        auto n = mRenderingState.mTextures[slot];
        if (!n)
            return;
        if (n->second.linear_filter != linear || n->second.cms != s || n->second.cmt != t) {
            Flush();
            if (rdp.loaded_texture[slot].blended)
                backend.SetSamplerParameters(4 + slot, linear, s, t);
            backend.SetSamplerParameters(slot, linear, s, t);
            n->second.linear_filter = linear;
            n->second.cms = (uint8_t)s;
            n->second.cmt = (uint8_t)t;
        }
    }
    void Framebuffer(unsigned id) {
        Flush();
        XboxInvalidateTextureBindings();
        backend.SelectTextureFb(id);
    }
    void External(unsigned id) {
        Flush();
        GetCurrentRenderingAPI()->SelectTexture(0, 2000 + id);
        backend.Upload(0xee0000 + id);
    }
    void Reset() {
        Flush();
        XboxInvalidateTextureBindings();
    }
};
// ENGINE_END
static void Same(Original &a, Projected &b) {
    a.Flush();
    b.Flush();
    Require(a.backend.output.size() == b.backend.output.size(), "draw count changed");
    for (size_t i = 0; i < a.backend.output.size(); ++i) {
        const Draw &x = a.backend.output[i];
        const Draw &y = b.backend.output[i];
        Require(x.shader == y.shader, "draw observed wrong shader");
        for (unsigned slot = 0; slot < 6; ++slot)
            Require(x.contents[slot] == y.contents[slot] && x.sampler[slot] == y.sampler[slot],
                    "draw observed wrong texture or sampler state");
    }
    Require(a.backend.uploads == b.backend.uploads, "real upload suppressed or duplicated");
    Require(a.imports == b.imports && a.masks == b.masks, "base/mask/replacement import skipped");
    Require(a.mTextureCache.map.size() == b.mTextureCache.map.size(), "cache membership changed");
    auto x = a.mTextureCache.lru.begin();
    auto y = b.mTextureCache.lru.begin();
    for (; x != a.mTextureCache.lru.end(); ++x, ++y)
        Require(x->it->first == y->it->first, "LRU order changed");
}
static uint8_t data[32][32];
static void Configure(Original &a, Projected &b, unsigned seed) {
    for (unsigned slot = 0; slot < 6; ++slot) {
        TextureCacheKey key = {data[(seed + slot) % 32], {NULL, NULL}, 0, 1, 0, 32, 0, 0, 8, 4};
        if (seed & 1) {
            key.palette_addrs[0] = data[(seed + 17) % 32];
            key.palette_index = (uint8_t)(seed % 16);
        }
        a.requests[slot] = b.requests[slot] = key;
    }
    for (unsigned slot = 0; slot < 2; ++slot) {
        a.rdp.loaded_texture[slot].masked = b.rdp.loaded_texture[slot].masked = true;
        a.rdp.loaded_texture[slot].blended = b.rdp.loaded_texture[slot].blended = true;
    }
}
int main() {
    for (unsigned i = 0; i < 32; ++i)
        for (unsigned j = 0; j < 32; ++j)
            data[i][j] = (uint8_t)(i * 17 + j);
    {
        Original a;
        Projected b;
        Configure(a, b, 0);
        a.requests[1] = a.requests[0];
        b.requests[1] = b.requests[0];
        a.AllImports();
        b.AllImports();
        a.Sampler(0, true, 1, 0);
        b.Sampler(0, true, 1, 0);
        a.Sampler(1, true, 2, 0);
        b.Sampler(1, true, 2, 0);
        a.AllImports();
        b.AllImports();
        a.Queue();
        b.Queue();
        Require(a.backend.nativeSampler[0] == 5, "reference did not restore aliased slot sampler");
        Require(b.backend.nativeSampler[0] == a.backend.nativeSampler[0], "aliased slot sampler was not recertified");
        Same(a, b);
    }
    // RED baseline: same six real imports must retain hashing/LRU, but neither
    // flush nor rebind the identical images while a triangle remains queued.
    {
        Original a;
        Projected b;
        Configure(a, b, 0);
        a.AllImports();
        b.AllImports();
        a.Queue();
        b.Queue();
        unsigned selects = b.backend.selects;
        hashCalls = 0;
        a.AllImports();
        unsigned ah = hashCalls;
        hashCalls = 0;
        b.AllImports();
        Require(ah == hashCalls && ah == 6, "content hash skipped on bound hit");
        Require(b.pending == 1 && b.backend.selects == selects, "same binding still flushes/reselects");
        Same(a, b);
    }
    unsigned cases = 0;
    // All clamp variants can first appear while identical texture imports
    // retain a queued batch. Compile failure also must drain the old batch
    // before backend Unload/Create changes its logical shader ownership.
    for (unsigned variant = 0; variant < 16; ++variant)
        for (unsigned failed = 0; failed < 2; ++failed) {
            Original a;
            Projected b;
            Configure(a, b, 0);
            a.AllImports();
            b.AllImports();
            a.backend.shader = b.backend.shader = 31;
            a.Queue();
            b.Queue();
            a.AllImports();
            b.AllImports();
            a.failShader = b.failShader = failed != 0;
            a.Shader(variant);
            b.Shader(variant);
            Require(a.pending == 0 && b.pending == 0, "shader creation did not finish prior program users");
            Require((a.combiner.prg[variant] == NULL) == (failed != 0) &&
                        (b.combiner.prg[variant] == NULL) == (failed != 0),
                    "failed program cached as success");
            Same(a, b);
            ++cases;
        }
    // Aliases must stay valid across shared-node sampler changes, then be
    // invalidated together before stale-byte eviction/recycled native IDs.
    for (unsigned options = 0; options < 256; ++options) {
        Original a;
        Projected b;
        Configure(a, b, options % 32);
        for (unsigned i = 0; i < 2; ++i) {
            a.rdp.loaded_texture[i].masked = b.rdp.loaded_texture[i].masked = (options & (1u << i)) != 0;
            a.rdp.loaded_texture[i].blended = b.rdp.loaded_texture[i].blended = (options & (4u << i)) != 0;
        }
        if (options & 16)
            a.requests[1] = b.requests[1] = a.requests[0];
        if (options & 32)
            a.requests[4] = b.requests[4] = a.requests[0];
        // Actual mask keys intentionally have no source-size verification.
        for (unsigned i = 2; i < 4; ++i) {
            auto key = a.requests[i];
            key.size_bytes = 0;
            key.fmt = key.siz = key.palette_index = key.masks = key.maskt = 0;
            key.tile_width = key.tile_height = 0;
            key.palette_addrs[0] = key.palette_addrs[1] = NULL;
            a.requests[i] = b.requests[i] = key;
        }
        verifyContent = (options & 64) == 0;
        for (unsigned repeat = 0; repeat < 8; ++repeat) {
            hashCalls = 0;
            a.AllImports();
            unsigned hashes = hashCalls;
            hashCalls = 0;
            b.AllImports();
            Require(hashes == hashCalls, "hash work changed for mask, alias or disabled-verification path");
            a.Queue();
            b.Queue();
            a.Sampler(1, (repeat & 1) != 0, repeat & 3, (repeat >> 1) & 3);
            b.Sampler(1, (repeat & 1) != 0, repeat & 3, (repeat >> 1) & 3);
            if (repeat == 2) {
                a.TextureCacheDelete(a.requests[0].texture_addr);
                b.TextureCacheDelete(b.requests[0].texture_addr);
            }
            if (repeat == 4) {
                data[options % 32][0] ^= 0x23;
            }
            if (repeat == 6) {
                a.TextureCacheDeleteRange(NULL, 7);
                b.TextureCacheDeleteRange(NULL, 7);
            }
            ++cases;
        }
        Same(a, b);
    }
    verifyContent = true;
    for (unsigned seed = 0; seed < 512; ++seed) {
        Original a;
        Projected b;
        Configure(a, b, seed);
        unsigned rng = seed + 1;
        for (unsigned step = 0; step < 256; ++step) {
            rng = rng * 1664525u + 1013904223u;
            unsigned action = (rng >> 24) % 12;
            if (action < 3) {
                a.AllImports();
                b.AllImports();
                a.Queue();
                b.Queue();
            } else if (action == 3) {
                unsigned j = rng % 32;
                data[j][rng % 32] ^= 0x51;
                a.AllImports();
                b.AllImports();
            } else if (action == 4) {
                Configure(a, b, rng % 32);
                a.AllImports();
                b.AllImports();
            } else if (action == 5) {
                a.TextureCacheClear();
                b.TextureCacheClear();
            } else if (action == 6) {
                a.TextureCacheDeleteRange(data[rng % 32], 32);
                b.TextureCacheDeleteRange(data[rng % 32], 32);
            } else if (action == 7) {
                a.Framebuffer(rng % 4);
                b.Framebuffer(rng % 4);
            } else if (action == 8) {
                a.External(rng % 4);
                b.External(rng % 4);
            } else if (action == 9) {
                a.Reset();
                b.Reset();
            } else if (action == 10) {
                unsigned slot = rng % 2;
                a.Sampler(slot, (rng & 4) != 0, (rng >> 4) & 3, (rng >> 6) & 3);
                b.Sampler(slot, (rng & 4) != 0, (rng >> 4) & 3, (rng >> 6) & 3);
            } else {
                a.AllImports();
                b.AllImports();
                a.Shader(rng % 16);
                b.Shader(rng % 16);
                a.Queue();
                b.Queue();
            }
            ++cases;
        }
        Same(a, b);
    }
    std::printf("PASS %u cache/import mutation steps: six bindings, hashes, queued draws, uploads, palette keys, LRU "
                "eviction, ID reuse, framebuffer/external reset and shader creation\n",
                cases);
}
