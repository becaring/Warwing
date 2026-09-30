// The reconciliation bodies below are extracted from the pinned interpreter,
// before and after the projection. This boundary fixture observes actual
// state/import/shader calls and output fields; texture cache internals are
// independently covered by texture_binding_contract.cpp.
#define ColorCombiner UpstreamColorCombiner
#include "fast/interpreter.h"
#include "fast3d/texture_bindings.h"
#include "fast3d/material_value_cache.h"
#include "fast3d/shader_metadata_cache.h"
#undef ColorCombiner
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <vector>

enum { SMASH_TRI_STATE, SMASH_TRI_COMBINER, SMASH_TRI_TEXTURE, SMASH_TRI_SHADER };
struct SmashTriangleTrace {
    unsigned phases;
    SmashTriangleTrace() : phases(0) {}
    void Mark(unsigned p) { phases = phases * 7 + p + 1; }
};

namespace Fast {
struct ShaderProgram {
    unsigned id;
    uint8_t numInputs;
    bool used[2];
};
// EXTRACTED_COMBINER
// CACHE_DECLARATIONS
// EXTRACTED_MATERIAL_HELPERS

struct BackendState {
    unsigned depth, color, decal, alpha, shader;
    XYWidthHeight viewport, scissor;
    unsigned textures[6], samplers[6][3];
};
struct Backend {
    BackendState state;
    std::vector<unsigned> events;
    std::map<std::pair<uint64_t, uint64_t>, ShaderProgram> programs;
    unsigned metadata;
    bool failed;
    Backend() : state(), metadata(0), failed(false) { state.color = 1; }
    void Event(unsigned n) { events.push_back(n); }
    void SetDepthTestAndMask(bool test, bool mask) {
        Event(10);
        state.depth = (test ? 1 : 0) | (mask ? 2 : 0);
    }
    void SetColorWriteMask(bool value) {
        Event(11);
        state.color = value;
    }
    void SetZmodeDecal(bool value) {
        Event(12);
        state.decal = value;
    }
    void SetUseAlpha(bool value) {
        Event(13);
        state.alpha = value;
    }
    void SetViewport(int x, int y, unsigned w, unsigned h) {
        Event(14);
        state.viewport = {short(x), short(y), w, h};
    }
    void SetScissor(int x, int y, unsigned w, unsigned h) {
        Event(15);
        state.scissor = {short(x), short(y), w, h};
    }
    void SetSamplerParameters(unsigned slot, bool linear, unsigned cms, unsigned cmt) {
        Event(20 + slot);
        state.samplers[slot][0] = linear;
        state.samplers[slot][1] = cms;
        state.samplers[slot][2] = cmt;
    }
    void UnloadShader(ShaderProgram *) {
        Event(30);
        state.shader = 0;
    }
    void LoadShader(ShaderProgram *program) {
        Event(31);
        state.shader = program->id;
    }
    void ShaderGetInfo(ShaderProgram *program, uint8_t *count, bool used[2]) {
        Event(32);
        ++metadata;
        *count = program->numInputs;
        used[0] = program->used[0];
        used[1] = program->used[1];
    }
};

struct Harness {
    RDP rdp;
    RSP rsp;
    RDP *mRdp;
    RSP *mRsp;
    Backend api;
    Backend *mRapi;
    RenderingState mRenderingState;
    GfxClipParameters mXboxClipParameters;
    std::stack<int16_t> mShaderStack;
    std::map<ColorCombinerKey, ColorCombiner> combiners;
    TextureCacheNode nodes[6];
    Shipyard::Fast3D::TextureBindings<SHADER_MAX_TEXTURES> mXboxTextureBindings;
    XboxTrianglePipelineKey mXboxPipelineKey;
    XboxTrianglePipelineResult mXboxPipelineResult;
    unsigned lookups, imports, masks, flushes;
    bool alias;
    Harness()
        : rdp(), rsp(), mRdp(&rdp), mRsp(&rsp), mRapi(&api), mRenderingState(), mXboxClipParameters(),
          mXboxPipelineResult(), lookups(0), imports(0), masks(0), flushes(0), alias(false) {
        mXboxClipParameters.z_is_from_0_to_1 = true;
        rdp.combine_mode = 3;
        for (unsigned i = 0; i < 8; ++i) {
            auto &tile = rdp.texture_tile[i];
            tile.fmt = G_IM_FMT_RGBA;
            tile.siz = G_IM_SIZ_16b;
            tile.tmem_index = i % 2;
            tile.line_size_bytes = 64;
            tile.lrs = tile.lrt = 124;
            tile.cms = tile.cmt = G_TX_CLAMP;
        }
        for (unsigned i = 0; i < 2; ++i) {
            auto &loaded = rdp.loaded_texture[i];
            loaded.size_bytes = 1024;
            loaded.line_size_bytes = 64;
            loaded.full_image_line_size_bytes = 64;
            loaded.orig_size_bytes = 1024;
        }
        for (unsigned i = 0; i < 6; ++i) {
            nodes[i].second.texture_id = i + 1;
            nodes[i].second.linear_filter = false;
            nodes[i].second.cms = nodes[i].second.cmt = 0;
            mRenderingState.mTextures[i] = &nodes[i];
            api.state.textures[i] = i + 1;
        }
    }
    bool RdpColorImageIsZBuffer() const {
        return (rdp.color_image_address != NULL && rdp.color_image_address == rdp.z_buf_address) ||
               (rdp.color_image_address_raw != 0 && rdp.color_image_address_raw == rdp.z_buf_address_raw);
    }
    void Flush() {
        ++flushes;
        api.Event(1);
    }
    ColorCombiner *LookupOrCreateColorCombiner(const ColorCombinerKey &key) {
        ++lookups;
        auto found = combiners.find(key);
        if (found != combiners.end())
            return &found->second;
        ColorCombiner comb = {};
        comb.shader_id0 = key.combine_mode;
        comb.shader_id1 = key.options;
        comb.usedTextures[0] = (key.combine_mode & 1) != 0;
        comb.usedTextures[1] = (key.combine_mode & 2) != 0;
        return &combiners.insert(std::make_pair(key, comb)).first->second;
    }
    ShaderProgram *LookupOrCreateShaderProgram(uint64_t id0, uint64_t id1) {
        api.Event(40);
        if (api.failed)
            return NULL;
        auto key = std::make_pair(id0, id1);
        auto found = api.programs.find(key);
        if (found != api.programs.end())
            return &found->second;
        ShaderProgram program = {
            unsigned(api.programs.size() + 1), uint8_t((id0 % 7) + 1), {(id0 & 1) != 0, (id0 & 2) != 0}};
        ShaderProgram *result = &api.programs.insert(std::make_pair(key, program)).first->second;
        // Native creation immediately binds, as the real Xenos API does.
        api.state.shader = result->id;
        return result;
    }
    void ImportTexture(unsigned slot, unsigned tile, bool replacement) {
        Flush();
        ++imports;
        api.Event(50 + slot);
        api.Event(tile);
        api.Event(replacement);
        auto *node = &nodes[alias && slot < 2 ? 0 : slot];
        mRenderingState.mTextures[slot] = node;
        api.state.textures[slot] = node->second.texture_id;
        mXboxTextureBindings.Selected(
            slot, node, node->second.texture_id,
            Shipyard::Fast3D::TextureSamplerState(node->second.linear_filter, node->second.cms, node->second.cmt));
    }
    void ImportTextureMask(unsigned slot, unsigned tile) {
        Flush();
        ++masks;
        api.Event(60 + slot);
        api.Event(tile);
    }
    void Reset() {
        Flush();
        mXboxPipelineKey.valid = false;
        mRenderingState.mShaderProgram = NULL;
        api.state.shader = 0;
    }
};
struct Original : Harness {
    bool Phase(SmashTriangleTrace &);
};
struct Projected : Harness {
    bool Phase(SmashTriangleTrace &);
    bool XboxPrepareTrianglePipeline(SmashTriangleTrace &);
};
// EXTRACTED_PHASES

static unsigned cases, hits;
static void Require(bool ok, const char *message) {
    if (!ok) {
        std::fprintf(stderr, "FAIL case=%u %s\n", cases, message);
        std::exit(1);
    }
}
static void CompareResult(const XboxTrianglePipelineResult &a, const XboxTrianglePipelineResult &b) {
    Require(a.ccId == b.ccId && a.tm == b.tm && a.alpha == b.alpha && a.fog == b.fog && a.grayscale == b.grayscale &&
                a.blendColor == b.blendColor && a.redirect == b.redirect && a.numInputs == b.numInputs,
            "pipeline scalar outputs");
    Require(a.clip.z_is_from_0_to_1 == b.clip.z_is_from_0_to_1 && a.clip.invertY == b.clip.invertY, "clip output");
    Require(a.comb->shader_id0 == b.comb->shader_id0 && a.comb->shader_id1 == b.comb->shader_id1, "combiner identity");
    for (unsigned i = 0; i < 2; ++i) {
        Require(a.usedTextures[i] == b.usedTextures[i] && a.effectiveTile[i] == b.effectiveTile[i],
                "texture usage outputs");
        Require(a.width[i] == b.width[i] && a.height[i] == b.height[i] && a.boundWidth[i] == b.boundWidth[i] &&
                    a.boundHeight[i] == b.boundHeight[i],
                "integer geometry outputs");
        Require(!std::memcmp(&a.widthFloat[i], &b.widthFloat[i], 4) &&
                    !std::memcmp(&a.heightFloat[i], &b.heightFloat[i], 4) &&
                    !std::memcmp(&a.boundWidthFloat[i], &b.boundWidthFloat[i], 4) &&
                    !std::memcmp(&a.boundHeightFloat[i], &b.boundHeightFloat[i], 4),
                "floating geometry outputs");
    }
}
static void Step(Original &a, Projected &b) {
    ++cases;
    bool hit = b.mXboxPipelineKey.Matches(b);
    if (hit)
        ++hits;
    a.api.events.clear();
    b.api.events.clear();
    SmashTriangleTrace x, y;
    const unsigned importsA = a.imports, importsB = b.imports, masksA = a.masks, masksB = b.masks;
    bool original = a.Phase(x), candidate = b.Phase(y);
    Require(original == candidate, "shader failure outcome");
    Require(x.phases == y.phases, "state/combiner/texture/shader observer order");
    // A hit may restore a byte-identical reload: the original re-imports the
    // node it already has bound, which the native state/dirty-flag checks below
    // must show as a no-op. Cold steps dispatch exactly the same imports.
    if (!hit)
        Require(a.imports - importsA == b.imports - importsB && a.masks - masksA == b.masks - masksB,
                "required texture hash/import dispatch omitted");
    else
        Require(b.imports == importsB && b.masks == masksB, "warm reconciliation imported");
    Require(a.rdp.textures_changed[0] == b.rdp.textures_changed[0] &&
                a.rdp.textures_changed[1] == b.rdp.textures_changed[1],
            "dirty flag behavior");
    Require(!std::memcmp(&a.api.state, &b.api.state, sizeof(BackendState)), "effective native state differs");
    if (!hit)
        Require(a.api.events == b.api.events, "cold native call/flush sequence changed");
    else
        Require(b.api.events.empty(), "warm reconciliation still calls native API");
    if (original)
        CompareResult(a.mXboxPipelineResult, b.mXboxPipelineResult);
}
static void Mutate(Harness &h, unsigned n) {
    switch (n % 16) {
    case 0:
        h.rdp.combine_mode = (n / 16) % 4;
        break;
    case 1:
        h.rdp.other_mode_l ^= Z_CMP | Z_UPD;
        h.rsp.geometry_mode ^= G_ZBUFFER;
        break;
    case 2:
        h.rdp.other_mode_h ^= G_TF_BILERP;
        break;
    case 3:
        h.rdp.viewport_or_scissor_changed = true;
        h.rdp.viewport.width = 320 + (n & 31);
        break;
    case 4:
        h.rdp.color_image_address_raw = h.rdp.z_buf_address_raw = (n & 16) ? 123 : 0;
        break;
    case 5:
        h.rdp.textures_changed[0] = h.rdp.textures_changed[1] = true;
        break;
    case 6:
        h.rdp.first_tile_index = (n / 16) % 8;
        break;
    // Same-tile image rectangles write geometry without a new tile selection.
    case 7:
        h.rdp.texture_tile[h.rdp.first_tile_index].lrs = 60 + float(n % 8);
        h.rdp.loaded_texture[h.rdp.texture_tile[h.rdp.first_tile_index].tmem_index].size_bytes = 512 + (n % 4) * 256;
        break;
    case 8:
        h.nodes[0].second.cms ^= G_TX_CLAMP;
        break;
    case 9:
        h.rdp.loaded_texture[0].masked = !h.rdp.loaded_texture[0].masked;
        h.rdp.textures_changed[0] = true;
        break;
    case 10:
        h.rdp.loaded_texture[1].blended = !h.rdp.loaded_texture[1].blended;
        h.rdp.textures_changed[1] = true;
        break;
    case 11:
        if (h.mShaderStack.empty())
            h.mShaderStack.push(short(n % 6));
        else
            h.mShaderStack.pop();
        break;
    case 12:
        h.Reset();
        break;
    case 13:
        h.rdp.grayscale = !h.rdp.grayscale;
        break;
    case 14:
        h.mRenderingState.decal_mode = !h.mRenderingState.decal_mode;
        break;
    case 15:
        h.rdp.other_mode_l ^= ZMODE_DEC;
        break;
    }
}
}
int main() {
    using namespace Fast;
    Original a;
    Projected b;
    for (unsigned i = 0; i < 4096; ++i) {
        Mutate(a, i);
        Mutate(b, i);
        Step(a, b);
        Step(a, b);
    }
    // Unused dirty texture remains dirty on every hit, then the real used-slot
    // import boundary must execute when a different combiner requires it.
    a.rdp.combine_mode = b.rdp.combine_mode = 1;
    a.rdp.textures_changed[1] = b.rdp.textures_changed[1] = true;
    Step(a, b);
    unsigned before = b.imports;
    Step(a, b);
    Require(b.rdp.textures_changed[1], "unused dirty flag cleared");
    a.rdp.combine_mode = b.rdp.combine_mode = 3;
    Step(a, b);
    Require(b.imports > before, "newly used dirty slot did not import");
    // Shared node sampler fields end with slot one's value. Each slot's native
    // sampler state must still match after warm reuse and direct node mutation.
    a.alias = b.alias = true;
    a.rdp.first_tile_index = b.rdp.first_tile_index = 0;
    a.rdp.texture_tile[0].cms = b.rdp.texture_tile[0].cms = G_TX_CLAMP;
    a.rdp.texture_tile[1].cms = b.rdp.texture_tile[1].cms = G_TX_WRAP;
    a.rdp.textures_changed[0] = a.rdp.textures_changed[1] = b.rdp.textures_changed[0] = b.rdp.textures_changed[1] =
        true;
    Step(a, b);
    for (unsigned i = 0; i < 32; ++i)
        Step(a, b);
    a.nodes[0].second.cmt ^= G_TX_CLAMP;
    b.nodes[0].second.cmt ^= G_TX_CLAMP;
    Step(a, b);
    // Failed shader creation cannot certify a result or reuse a stale success.
    a.Reset();
    b.Reset();
    a.combiners.clear();
    b.combiners.clear();
    a.api.failed = b.api.failed = true;
    Step(a, b);
    Require(!b.mXboxPipelineKey.valid, "failed shader certified");
    Step(a, b);
    a.api.failed = b.api.failed = false;
    Step(a, b);
    Step(a, b);
    Require(hits > 4000, "no useful pipeline reuse");
    std::printf("PASS %u extracted real reconciliation steps; %u warm hits, exact cold native calls/outputs, same-tile "
                "geometry, sampler alias, unused-to-used dirty, reset and shader failure\n",
                cases, hits);
}
