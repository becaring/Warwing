#include "fast/interpreter.h"
#include "fast3d/vertex_lighting.h"
#include "fast3d/normal_sources.h"
#include "fast3d/vertex_transform.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <cstdlib>

namespace Ship { namespace Math {
// EXTRACTED_SHIP_CLAMP
}}
namespace Fast {
static unsigned observedShadeReuse;
static_assert(sizeof(F3DVtx)==16 && offsetof(F3DVtx_tn,n)==12,"donor source layout");
// Use the authoritative complete RSP/F3DVtx/LoadedVertex types. The harness
// supplies only the Interpreter fields read by the extracted production body.
#define HARNESS(name) struct name { \
    RSP* mRsp; bool mFbActive; bool mWidescreenActive; XYWidthHeight mGameWindowViewport; \
    static void NormalizeVector(float v[3]); \
    static void TransposedMatrixMul(float res[3],const float a[3],const float b[4][4]); \
    void CalculateNormalDir(const F3DLight_t* light,float coeffs[3]); \
    float GetWidescreenClipXScale() const; \
    float AdjXForAspectRatio(float x) const; \
    void GfxSpVertex(size_t n_vertices,size_t dest_index,const F3DVtx* vertices); \
};
HARNESS(Original)
HARNESS(Projected)
#undef HARNESS
// EXTRACTED_FUNCTIONS
}
// EXTRACTED_ACCUMULATION

static void require(bool pass,const char* message) {
    if(!pass) { std::fprintf(stderr,"FAIL: %s\n",message); std::exit(1); }
}
static bool same(float a,float b) { return std::memcmp(&a,&b,sizeof(a))==0; }
static float fromBits(uint32_t bits) { float value; std::memcpy(&value,&bits,sizeof(value)); return value; }

static void compareVertex(Fast::RSP before,const Fast::F3DVtx* vertices,unsigned count,unsigned seed) {
    std::memset(before.loaded_vertices,0xA5,sizeof(before.loaded_vertices));
    Fast::RSP after=before;
    Fast::Original a={&before,(seed&2)!=0,(seed&4)!=0,{0,0,1280,720}};
    Fast::Projected b={&after,a.mFbActive,a.mWidescreenActive,a.mGameWindowViewport};
    a.GfxSpVertex(count,3,vertices);b.GfxSpVertex(count,3,vertices);
    require(std::memcmp(&before,&after,sizeof(before))==0,"real vertex output/state mismatch");
}

static unsigned exceptionalCases() {
    // Inputs are runtime data, including nonfinite values. For out-of-range
    // float-to-int casts this compares the ACTUAL original/projected compiler
    // behavior, without imposing a made-up portable overflow result.
    const uint32_t inputs[]={0,0x80000000,1,0x007fffff,0x3f19999a,0x3f800000,
        0x447fffff,0x44800000,0x44800001,0x4affffff,0x4b000000,0x4effffff,
        0x4f000000,0x7f7fffff,0x7f800000,0xff800000,0x7fc00001,0x7f800001,
        0xbf800000,0xff7fffff};
    const unsigned counts[]={1,2,4,33,34,255};
    unsigned cases=0;
    uint8_t colors[256][3];float intensities[256];
    for(unsigned seed=0;seed<16;++seed)for(unsigned lc=0;lc<6;++lc)
    for(unsigned value=0;value<sizeof(inputs)/sizeof(inputs[0]);++value)
    for(unsigned placement=0;placement<4;++placement) {
        const unsigned count=counts[lc];
        for(unsigned light=0;light<count;++light) {
            for(unsigned channel=0;channel<3;++channel)
                colors[light][channel]=seed==0?255:seed==1?1:seed==2?0:(uint8_t)(seed+light*23+channel*91);
            intensities[light]=0.6f;
        }
        if(placement==0) for(unsigned light=0;light+1<count;++light) intensities[light]=fromBits(inputs[value]);
        else if(count>1) intensities[placement==1?0:placement==2?(count-2)/2:count-2]=fromBits(inputs[value]);
        int original[3],projected[3];
        AccumulationOriginal(colors,intensities,(uint8_t)count,original);
        AccumulationProjected(colors,intensities,(uint8_t)count,projected);
        if(std::memcmp(original,projected,sizeof(original))!=0) {
            std::fprintf(stderr,"accum mismatch seed=%u count=%u input=%08x placement=%u before=%d,%d,%d after=%d,%d,%d\n",
                seed,count,inputs[value],placement,original[0],original[1],original[2],projected[0],projected[1],projected[2]);
            require(false,"unsaturated integer channel mismatch");
        }
        ++cases;
        if(count<=33) {
            Fast::RSP rsp={};
            rsp.modelview_matrix_stack_size=1;
            for(unsigned axis=0;axis<4;++axis) {
                rsp.modelview_matrix_stack[0][axis][axis]=1.0f;
                rsp.MP_matrix[axis][axis]=1.0f;
            }
            rsp.current_num_lights=(uint8_t)count;rsp.geometry_mode=G_LIGHTING;
            for(unsigned light=0;light<count;++light) {
                for(unsigned channel=0;channel<3;++channel) rsp.current_lights[light].l.col[channel]=colors[light][channel];
                if(light+1<count) rsp.current_lights_coeffs[light][0]=intensities[light];
            }
            Fast::F3DVtx vertex={};vertex.n.n[0]=127;vertex.n.a=255;
            compareVertex(rsp,&vertex,1,seed);
            ++cases;
        }
    }
    // Per-contribution truncation is observable before saturation: accumulating
    // 32 * 0.6 and truncating only at the end would incorrectly produce 19.
    std::memset(colors,1,sizeof(colors));std::memset(colors[32],0,3);
    for(unsigned light=0;light<32;++light) intensities[light]=0.6f;
    int totals[3];AccumulationProjected(colors,intensities,33,totals);
    require(totals[0]==0&&totals[1]==0&&totals[2]==0,"lost per-contribution truncation");
    return cases;
}

int main() {
    for(unsigned bits=0;bits<65536;++bits) {
        volatile int16_t s=(int16_t)bits;volatile uint16_t u=(uint16_t)bits;
        require(same((float)s,Smash360Fast::SignedShortFloat(s)),"signed short conversion");
        require(same((float)u,Smash360Fast::UnsignedShortFloat(u)),"unsigned short conversion");
    }
    for(unsigned byte=0;byte<256;++byte) {
        volatile unsigned char u=(unsigned char)byte;
        volatile signed char s=(signed char)byte;
        require(same((float)u,Smash360Fast::LightByteFloat(u)),"unsigned byte conversion");
        require(same((float)s,Smash360Fast::NormalByteFloat(s)),"signed byte conversion");
    }
    unsigned cases=0;
    const unsigned lightCounts[]={1,2,4,33};
    for(unsigned seed=0;seed<256;++seed)for(unsigned mode=0;mode<32;++mode)for(unsigned lc=0;lc<4;++lc) {
        Fast::RSP before={};
        before.modelview_matrix_stack_size=1;
        for(unsigned axis=0;axis<4;++axis) {
            before.modelview_matrix_stack[0][axis][axis]=1.0f;
            before.MP_matrix[axis][axis]=1.0f;
        }
        before.MP_matrix[3][3]=64.0f;
        before.current_num_lights=(uint8_t)lightCounts[lc];
        before.geometry_mode=(mode&1?G_LIGHTING:0)|(mode&2?G_LIGHTING_POSITIONAL:0)|
            (mode&4?G_TEXTURE_GEN:0)|(mode&8?G_TEXTURE_GEN_LINEAR:0)|(mode&16?G_FOG:0);
        before.lights_changed=(seed&1)!=0;
        before.lookat[0].dir[0]=127;before.lookat[1].dir[1]=127;
        before.current_lookat_coeffs[0][0]=1.0f;before.current_lookat_coeffs[1][1]=1.0f;
        before.texture_scaling_factor.s=(uint16_t)(seed*257);
        before.texture_scaling_factor.t=(uint16_t)(65535-seed*257);
        before.fog_mul=(int16_t)(seed*257);before.fog_offset=(int16_t)(32767-seed*257);
        for(unsigned light=0;light<before.current_num_lights;++light) {
            Fast::F3DLight& l=before.current_lights[light];
            for(unsigned channel=0;channel<3;++channel) {
                l.l.col[channel]=(uint8_t)(seed+light*23+channel*91);
                l.l.dir[channel]=(int8_t)(seed+light*37+channel*79);
                before.current_lights_coeffs[light<MAX_LIGHTS?light:0][channel]=
                    ((int)((seed+light*37+channel*79)&255)-128)/128.0f;
            }
            if((mode&2)&&(light&1)) {
                l.p.unk3=1;l.p.unk7=(uint8_t)seed;l.p.unkE=(uint8_t)(255-seed);
                l.p.pos[0]=800;l.p.pos[1]=900;l.p.pos[2]=1000;
            } else l.p.unk3=0;
        }
        Fast::F3DVtx vertices[8]={};
        for(unsigned index=0;index<8;++index) {
            for(unsigned axis=0;axis<3;++axis) {
                vertices[index].v.ob[axis]=(int16_t)((int)seed-128+(int)index*3+(int)axis*11);
                vertices[index].n.n[axis]=(int8_t)(seed+index*31+axis*91);
            }
            vertices[index].n.a=(uint8_t)seed;
            vertices[index].v.tc[0]=(int16_t)(seed*257);
            vertices[index].v.tc[1]=(int16_t)(65535-seed*257);
        }
        compareVertex(before,vertices,8,seed);
        // Identical normals with deliberately different positions, ordinary
        // UVs and alpha must share only the eligible directional RGB/texgen.
        for(unsigned index=1;index<8;++index) {
            if((index&1)==0 || (seed&1))std::memcpy(vertices[index].n.n,vertices[0].n.n,3);
            vertices[index].n.a=(uint8_t)(seed+index*19);
            vertices[index].v.tc[0]=(int16_t)(seed*257+index*997);
            vertices[index].v.tc[1]=(int16_t)(65535-seed*257-index*1193);
        }
        unsigned reuseBefore=Fast::observedShadeReuse;
        compareVertex(before,vertices,8,seed);
        if((mode&1) && !(mode&2))require(Fast::observedShadeReuse>reuseBefore,"normal reuse not exercised");
        else require(Fast::observedShadeReuse==reuseBefore,"reused unlit/positional results");
        ++cases;
    }
    const unsigned edges=exceptionalCases();
    std::printf("PASS: all 256 signed/unsigned byte conversions; %u real vertex/light cases, positional/texgen/fog, 1/2/4/33 lights, output/state/canaries; %u bound/exception/fallback cases, unsaturated totals and real vertices\n",cases,edges);
    return 0;
}
