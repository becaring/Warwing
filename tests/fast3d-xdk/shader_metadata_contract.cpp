#include "fast/interpreter.h"
#include "fast3d/shader_metadata_cache.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <type_traits>

namespace Fast {
// The production interface leaves ShaderProgram opaque. Its metadata below
// uses BattleShip's real CCFeatures type; no graphics output is replaced.
struct ShaderProgram {
    CCFeatures features;
    unsigned id;
};
// EXTRACTED_COMBINERS
static_assert(std::is_trivial<ProjectedCombiner>::value, "combiner must retain trivial zero initialization");

struct Result {
    bool valid;
    uint8_t inputs;
    bool used[2];
    GfxClipParameters clip;
};
struct Backend {
    ShaderProgram programs[16];
    unsigned infos, clips, events;
    bool failed;
    GfxClipParameters clip;
    Backend() : infos(0), clips(0), events(0), failed(false) { Reset(0); }
    void Reset(unsigned seed) {
        std::memset(programs, 0, sizeof(programs));
        for (unsigned i = 0; i < 16; ++i) {
            programs[i].id = i + 1;
            programs[i].features.numInputs = (i + seed) % 8;
            programs[i].features.usedTextures[0] = ((i + seed) & 1) != 0;
            programs[i].features.usedTextures[1] = ((i + seed) & 2) != 0;
        }
        clip.z_is_from_0_to_1 = (seed & 1) != 0;
        clip.invertY = (seed & 2) != 0;
    }
    void Init() {}
    void Event(unsigned value) { events = events * 31 + value; }
    void UnloadShader(ShaderProgram *p) { Event(100 + (p ? p->id : 0)); }
    void LoadShader(ShaderProgram *p) { Event(200 + p->id); }
    void SetUseAlpha(bool alpha) { Event(300 + alpha); }
    void ShaderGetInfo(ShaderProgram *p, uint8_t *count, bool used[2]) {
        if (!p)
            std::abort();
        ++infos;
        *count = (uint8_t)p->features.numInputs;
        used[0] = p->features.usedTextures[0];
        used[1] = p->features.usedTextures[1];
    }
    GfxClipParameters GetClipParameters() {
        ++clips;
        return clip;
    }
};
template <class Combiner> struct Harness {
    Backend *mRapi;
    RenderingState mRenderingState;
    GfxClipParameters mXboxClipParameters;
    std::map<unsigned, Combiner> mColorCombinerPool;
    Result result;
    Harness() : mRapi(NULL), mRenderingState(), mXboxClipParameters(), result() {}
    void Flush() { mRapi->Event(400); }
    ShaderProgram *LookupOrCreateShaderProgram(uint64_t, uint64_t key) {
        unsigned variant = (unsigned)(key / SHADER_OPT(TEXEL0_CLAMP_S)) & 15;
        mRapi->Event(500 + variant);
        if (mRapi->failed)
            return NULL;
        return &mRapi->programs[variant];
    }
};
struct Original : Harness<OriginalCombiner> {
    typedef OriginalCombiner ColorCombiner;
    void Phase(unsigned, bool);
    void Init(Backend *);
};
struct Projected : Harness<ProjectedCombiner> {
    typedef ProjectedCombiner ColorCombiner;
    void Phase(unsigned, bool);
    void Init(Backend *);
};
// EXTRACTED_FUNCTIONS
}
static void Require(bool ok, const char *message) {
    if (!ok) {
        std::fprintf(stderr, "FAIL %s\n", message);
        std::exit(1);
    }
}

int main() {
    Fast::Backend a[2], b[2];
    Fast::Original original;
    Fast::Projected projected;
    unsigned cases = 0;
    for (unsigned epoch = 0; epoch < 8; ++epoch) {
        unsigned which = epoch % 2;
        // Same-address backend reinitialization changes the metadata/clip
        // fixture only at the real Init boundary, never for a live program.
        a[which].Reset(epoch);
        b[which].Reset(epoch);
        original.Init(&a[which]);
        projected.Init(&b[which]);
        unsigned initialInfo = b[which].infos, initialClips = b[which].clips;
        for (unsigned n = 0; n < 4096; ++n) {
            unsigned variant = n % 16;
            bool alpha = ((n / 32) & 1) != 0;
            if (n == 1024 || n == 2048) {
                // Real filter/sRGB invalidation clears the combiner pool.
                original.mColorCombinerPool.clear();
                projected.mColorCombinerPool.clear();
            }
            if (n == 3072) {
                // In-place variant replacement must refresh actual metadata.
                original.mColorCombinerPool[0].prg[0] = &a[which].programs[1];
                projected.mColorCombinerPool[0].prg[0] = &b[which].programs[1];
            }
            original.result.valid = projected.result.valid = false;
            original.Phase(variant, alpha);
            projected.Phase(variant, alpha);
            Require(original.result.valid == projected.result.valid, "failure path");
            Require(original.result.inputs == projected.result.inputs, "shader inputs");
            Require(original.result.used[0] == projected.result.used[0] &&
                        original.result.used[1] == projected.result.used[1],
                    "used textures");
            Require(original.result.clip.z_is_from_0_to_1 == projected.result.clip.z_is_from_0_to_1 &&
                        original.result.clip.invertY == projected.result.clip.invertY,
                    "clip parameters");
            Require(a[which].events == b[which].events, "flush/bind/alpha event sequence");
            ++cases;
        }
        Require(b[which].infos - initialInfo == 49, "immutable shader metadata still queried every triangle");
        Require(b[which].clips == initialClips, "clip parameters still queried every triangle");
        // Retain a successfully certified node/program across Init. The later
        // failure case clears the pool, so it cannot exercise this boundary.
        original.Phase(1, true);
        projected.Phase(1, true);
        Fast::ShaderProgram *retained = projected.mColorCombinerPool[0].prg[1];
        unsigned beforeInitInfos = b[which].infos, beforeInitClips = b[which].clips;
        a[which].Reset(epoch + 19);
        b[which].Reset(epoch + 19);
        original.Init(&a[which]);
        projected.Init(&b[which]);
        Require(projected.mColorCombinerPool[0].prg[1] == retained, "Init changed authoritative program binding");
        original.Phase(1, true);
        projected.Phase(1, true);
        Require(original.result.inputs == projected.result.inputs &&
                    original.result.used[0] == projected.result.used[0] &&
                    original.result.used[1] == projected.result.used[1],
                "retained metadata survived same-address backend Init");
        Require(original.result.clip.z_is_from_0_to_1 == projected.result.clip.z_is_from_0_to_1 &&
                    original.result.clip.invertY == projected.result.clip.invertY,
                "retained clip survived backend Init");
        Require(b[which].infos == beforeInitInfos + 1, "Init did not refresh retained metadata exactly once");
        Require(b[which].clips == beforeInitClips + 1, "Init did not refresh clip exactly once");
        Require(a[which].events == b[which].events, "same-address Init changed state event sequence");
        original.Phase(1, true);
        projected.Phase(1, true);
        Require(b[which].infos == beforeInitInfos + 1, "reinitialized metadata not reused");
        cases += 3;
        original.mColorCombinerPool.clear();
        projected.mColorCombinerPool.clear();
        a[which].failed = b[which].failed = true;
        original.result.valid = projected.result.valid = false;
        unsigned infos = b[which].infos;
        original.Phase(7, true);
        projected.Phase(7, true);
        Require(!original.result.valid && !projected.result.valid, "failed shader did not return");
        Require(b[which].infos == infos, "queried metadata for failed shader");
        Require(a[which].events == b[which].events, "failed shader event sequence");
        a[which].failed = b[which].failed = false;
    }
    std::printf("PASS %u real shader-state cases: 16 variants, exact flush/bind/alpha order, metadata reuse, "
                "replacement, failure, filter reset and backend reinit\n",
                cases);
}
