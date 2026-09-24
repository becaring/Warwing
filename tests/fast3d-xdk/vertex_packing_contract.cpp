#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "fast3d/unit_color.h"
#include "fast3d/material_value_cache.h"
struct RGBA { uint8_t r,g,b,a; };
struct Vertex {float x,y,z,w,u,v;RGBA color;};
struct Tile {int shifts,shiftt;float uls,ult;};
struct RDP {Tile texture_tile[8];uint32_t other_mode_h,other_mode_l;
    RGBA blend_color,fog_color,grayscale_color,prim_color,env_color;uint8_t prim_lod_fraction;};
struct FbUvTransform {float scaleU,scaleV,offsetU,offsetV;};
enum {G_MDSFT_TEXTFILT=12,G_TF_POINT=0,G_BL_A_FOG=1,G_TL_LOD=1<<16,
    G_CCMUX_PRIMITIVE=3,G_CCMUX_SHADE=4,G_CCMUX_ENVIRONMENT=5,G_CCMUX_PRIMITIVE_ALPHA=10,
    G_CCMUX_ENV_ALPHA=12,G_CCMUX_PRIM_LOD_FRAC=14,G_CCMUX_LOD_FRACTION=13,G_ACMUX_PRIM_LOD_FRAC=6};
struct Combiner {int shader_input_mapping[2][7];
// COMBINER_FIELDS
};
typedef Vertex LoadedVertex;typedef Combiner ColorCombiner;
struct Harness {
    Vertex *v_arr[3],*v1; RDP* mRdp; Combiner* comb;
    bool use_prim_depth,is_rect,use_fog,use_blend_color,use_grayscale,use_alpha;
    struct {bool z_is_from_0_to_1,invertY;} clip_parameters;
    float prim_depth_ndc;bool usedTextures[2];uint32_t effective_tile[2];
    uint32_t tex_width[2],tex_height[2],tex_width2[2],tex_height2[2];
    float xboxTextureWidth[2],xboxTextureHeight[2],xboxTextureBoundWidth[2],xboxTextureBoundHeight[2];
    FbUvTransform mFbUvTransform[2];int tm,numInputs;
    float* mBufVbo;size_t mBufVboLen;
    void Original();void Projected();
};
static unsigned constantBuilds=0;
// EXTRACTED_FUNCTIONS
static uint32_t state=42;
static uint32_t Next(){state=1664525U*state+1013904223U;return state;}
static RGBA Color(){RGBA c={(uint8_t)Next(),(uint8_t)Next(),(uint8_t)Next(),(uint8_t)Next()};return c;}
int main(){
    for(unsigned i=0;i<256;i++) {volatile uint8_t input=(uint8_t)i;volatile float divisor=255.0f;
        float expected=input/divisor,actual=Shipyard::Fast3D::UnitColor(input);
        if(memcmp(&expected,&actual,4)){printf("color mismatch %u\n",i);return 1;}}
    const int selectors[]={G_CCMUX_PRIMITIVE,G_CCMUX_SHADE,G_CCMUX_ENVIRONMENT,G_CCMUX_PRIMITIVE_ALPHA,
        G_CCMUX_ENV_ALPHA,G_CCMUX_PRIM_LOD_FRAC,G_CCMUX_LOD_FRACTION,0};
    // GenerateCC rewrites alpha LOD selectors; RGB-only selectors initialize
    // tmp.rgb, not tmp.a, and are not legal alpha mappings for this packer.
    const int alphaSelectors[]={G_CCMUX_PRIMITIVE,G_CCMUX_SHADE,G_CCMUX_ENVIRONMENT,
        G_CCMUX_LOD_FRACTION,G_ACMUX_PRIM_LOD_FRAC,0};
    for(unsigned n=0;n<65536;n++) {
        Vertex vertices[3];RDP rdp={};Combiner combiner={};Harness a={};
        float original[512],projected[512];memset(original,0xa5,sizeof(original));memset(projected,0xa5,sizeof(projected));
        a.mBufVbo=original;a.mBufVboLen=7;a.mRdp=&rdp;a.comb=&combiner;
        a.use_prim_depth=!!(n&1);a.is_rect=!!(n&2);a.use_fog=!!(n&4);a.use_blend_color=!!(n&8);
        a.use_grayscale=!!(n&16);a.use_alpha=!!(n&32);a.clip_parameters.invertY=!!(n&64);
        a.clip_parameters.z_is_from_0_to_1=!!(n&128);a.tm=(n>>8)&15;a.numInputs=(n>>12)%8;a.prim_depth_ndc=0.125f;
        a.usedTextures[0]=!!(n&16384);a.usedTextures[1]=!!(n&32768);
        for(unsigned i=0;i<3;i++){Vertex& v=vertices[i];v.x=(int16_t)Next();v.y=(int16_t)Next();v.z=(int16_t)Next();
            v.w=(float)(Next()%7000);v.u=(int16_t)Next();v.v=(int16_t)Next();v.color=Color();a.v_arr[i]=&v;}
        a.v1=&vertices[0];rdp.other_mode_h=(n%3)<<G_MDSFT_TEXTFILT;rdp.other_mode_l=((n%4)<<26)|((n%2)?G_TL_LOD:0);
        rdp.blend_color=Color();rdp.fog_color=Color();rdp.grayscale_color=Color();rdp.prim_color=Color();rdp.env_color=Color();rdp.prim_lod_fraction=(uint8_t)Next();
        for(unsigned t=0;t<2;t++){a.effective_tile[t]=t;rdp.texture_tile[t].shifts=(n+t)%16;rdp.texture_tile[t].shiftt=(n/16+t)%16;
            rdp.texture_tile[t].uls=(uint16_t)Next();rdp.texture_tile[t].ult=(uint16_t)Next();
            if(n&4) {rdp.texture_tile[t].uls=rdp.texture_tile[t].uls*0.25f-8192.0f;rdp.texture_tile[t].ult=rdp.texture_tile[t].ult*0.125f-4096.0f;}
            a.tex_width[t]=1+Next()%2048;a.tex_height[t]=1+Next()%1024;a.tex_width2[t]=Next()%2048;a.tex_height2[t]=Next()%1024;
            if(n%32==0){a.tex_width[t]=0x80000001U;a.tex_height[t]=0xffffffffU;a.tex_width2[t]=0xffffffffU;a.tex_height2[t]=0x01000001U;}
            a.xboxTextureWidth[t]=(float)a.tex_width[t];a.xboxTextureHeight[t]=(float)a.tex_height[t];
            a.xboxTextureBoundWidth[t]=(float)a.tex_width2[t];a.xboxTextureBoundHeight[t]=(float)a.tex_height2[t];
            a.mFbUvTransform[t].scaleU=(n&1)?1.0f:0.25f;a.mFbUvTransform[t].scaleV=(n&2)?1.0f:0.5f;
            a.mFbUvTransform[t].offsetU=(n&4)?0.0f:0.125f;a.mFbUvTransform[t].offsetV=(n&8)?0.0f:0.0625f;}
        for(int j=0;j<7;j++){combiner.shader_input_mapping[0][j]=selectors[(n+j)%8];
            combiner.shader_input_mapping[1][j]=alphaSelectors[(n+j)%6];}
        Harness b=a;b.mBufVbo=projected;a.Original();b.Projected();
        // Keep the certificate alive across shade/fog, material and LOD changes.
        for(unsigned repeat=0;repeat<8;++repeat) {
            const unsigned previousBuilds=constantBuilds;
            for(unsigned vi=0;vi<3;++vi)vertices[vi].color=Color();
            if(repeat==1)rdp.prim_color=Color();
            if(repeat==2)rdp.env_color=Color();
            if(repeat==3)rdp.prim_lod_fraction^=127;
            if(repeat==4)vertices[0].w+=13.0f;
            if(repeat==5)rdp.other_mode_l^=G_TL_LOD;
            if(repeat==6)a.use_alpha=b.use_alpha=!a.use_alpha;
            if(repeat==7)a.use_fog=b.use_fog=!a.use_fog;
            a.mBufVboLen=b.mBufVboLen=7;
            memset(original,0xa5,sizeof(original));memset(projected,0xa5,sizeof(projected));
            a.Original();b.Projected();
            if(repeat==0 && previousBuilds!=constantBuilds){puts("shade rebuilt constants");return 4;}
            if(a.mBufVboLen!=b.mBufVboLen || memcmp(original,projected,sizeof(original))) {
                printf("cached packing mismatch %u repeat %u\n",n,repeat);return 3;
            }
        }
        if(a.mBufVboLen!=b.mBufVboLen || memcmp(original,projected,sizeof(original))) {printf("packing mismatch %u len %u/%u\n",n,(unsigned)a.mBufVboLen,(unsigned)b.mBufVboLen);return 2;}
    }
    puts("PASS 256 exact colors and 589824 original/projected vertex streams with live constant-cache mutations including prefix/tail guards");return 0;
}
