#include "fast/interpreter.h"
#include "fast3d/material_value_cache.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <float.h>

namespace Fast {
static unsigned geometryBuilds, optionBuilds;
// GENERATED_HELPERS
struct Harness {
    RDP* mRdp;
    unsigned i, tile, tm;
    uint32_t tex_width[2],tex_height[2],tex_width2[2],tex_height2[2];
    float xboxTextureWidth[2],xboxTextureHeight[2],xboxTextureBoundWidth[2],xboxTextureBoundHeight[2];
    uint64_t options_out;
    bool alpha,fog,blend,gray;
    uint8_t cms_out,cmt_out;
    void Original(); void Projected();
};
// EXTRACTED_FUNCTIONS
static void require(bool good,const char* msg) {
    if(!good){std::fprintf(stderr,"FAIL %s\n",msg);std::exit(1);}
}
static uint32_t randomState=0x351810fe;
static uint32_t Next(){randomState^=randomState<<13;randomState^=randomState>>17;return randomState^=randomState<<5;}
static void Compare(RDP& rdp,unsigned slot,unsigned tile) {
    Harness a={};a.mRdp=&rdp;a.i=slot;a.tile=tile;a.tm=0xa5a50000;
    Harness b=a;a.Original();b.Projected();
    require(a.tm==b.tm,"clamp mask including prior slot bits");
    require(!std::memcmp(a.tex_width,b.tex_width,sizeof(a.tex_width)),"width and inactive slot");
    require(!std::memcmp(a.tex_height,b.tex_height,sizeof(a.tex_height)),"height and inactive slot");
    require(!std::memcmp(a.tex_width2,b.tex_width2,sizeof(a.tex_width2)),"tile width and inactive slot");
    require(!std::memcmp(a.tex_height2,b.tex_height2,sizeof(a.tex_height2)),"tile height and inactive slot");
    require(!std::memcmp(a.xboxTextureWidth,b.xboxTextureWidth,sizeof(a.xboxTextureWidth)),"float width");
    require(!std::memcmp(a.xboxTextureHeight,b.xboxTextureHeight,sizeof(a.xboxTextureHeight)),"float height");
    require(!std::memcmp(a.xboxTextureBoundWidth,b.xboxTextureBoundWidth,sizeof(a.xboxTextureBoundWidth)),"float tile width");
    require(!std::memcmp(a.xboxTextureBoundHeight,b.xboxTextureBoundHeight,sizeof(a.xboxTextureBoundHeight)),"float tile height");
    require(a.options_out==b.options_out && a.alpha==b.alpha && a.fog==b.fog && a.blend==b.blend && a.gray==b.gray,"draw options");
    require(a.cms_out==b.cms_out && a.cmt_out==b.cmt_out,"sampler modes");
}
int Test() {
    RDP rdp={};
    unsigned cases=0;
    for(unsigned n=0;n<131072;++n) {
        unsigned tile=n%8,slot=(n>>3)%2;
        auto& t=rdp.texture_tile[tile]; t.tmem_index=(n>>4)%2;
        auto& l=rdp.loaded_texture[t.tmem_index];
        t.fmt=(n>>5)%5;t.siz=(n>>8)%4;t.cms=(n>>10)%4;t.cmt=(n>>12)%4;
        t.masks=Next()%16;t.maskt=Next()%16;
        t.uls=(int(Next()%8192)-4096)*0.25f;t.ult=(int(Next()%8192)-4096)*0.25f;
        t.lrs=(int(Next()%8192)-4096)*0.25f;t.lrt=(int(Next()%8192)-4096)*0.25f;
        t.line_size_bytes=Next()%4097;l.line_size_bytes=(n&1)?Next()%4097:0;
        l.size_bytes=Next()%65537;l.full_image_line_size_bytes=(n&2)?l.size_bytes:Next()%4097;
        if(n&4)l.line_size_bytes=l.size_bytes;
        l.orig_size_bytes=Next()%65537;
        rdp.other_mode_l=Next();rdp.other_mode_h=Next();rdp.grayscale=!!(n&1);
        Compare(rdp,slot,tile);++cases;
        unsigned g=geometryBuilds,o=optionBuilds;
        Compare(rdp,slot,tile);++cases;
        require(g==geometryBuilds && o==optionBuilds,"identical material must reuse values");
        // Every dependency changed individually: catches omissions in cache keys.
#define MUTATE_G(field) { Compare(rdp,slot,tile); ++cases; auto saved=field; unsigned before=geometryBuilds; field=decltype(field)(field+1); Compare(rdp,slot,tile); ++cases; require(geometryBuilds==before+1,"geometry key dependency rebuilds"); field=saved; }
#define MUTATE_O(field) { Compare(rdp,slot,tile); ++cases; auto saved=field; unsigned before=optionBuilds; field=decltype(field)(field+1); Compare(rdp,slot,tile); ++cases; require(optionBuilds==before+1,"options key dependency rebuilds"); field=saved; }
        MUTATE_G(t.fmt);MUTATE_G(t.siz);MUTATE_G(t.cms);MUTATE_G(t.cmt);
        t.masks%=15;t.maskt%=15;MUTATE_G(t.masks);MUTATE_G(t.maskt);
        MUTATE_G(t.uls);MUTATE_G(t.ult);MUTATE_G(t.lrs);MUTATE_G(t.lrt);MUTATE_G(t.line_size_bytes);
        MUTATE_G(l.line_size_bytes);MUTATE_G(l.size_bytes);MUTATE_G(l.full_image_line_size_bytes);MUTATE_G(l.orig_size_bytes);
        MUTATE_O(rdp.other_mode_l);MUTATE_O(rdp.other_mode_h);
#undef MUTATE_G
#undef MUTATE_O
        Compare(rdp,slot,tile);++cases;rdp.grayscale=!rdp.grayscale;Compare(rdp,slot,tile);++cases;
        // Source identity is not a dependency: same complete values in a
        // different RDP/texture address must be safe (no retained pointers).
        RDP other=rdp;Compare(other,slot,tile);++cases;
    }
    // Negative zero and fractional extents use the original float-to-int order.
    rdp.texture_tile[0].uls=-0.0f;rdp.texture_tile[0].ult=0.0f;
    Compare(rdp,0,0);rdp.texture_tile[0].uls=0.0f;Compare(rdp,0,0);
    unsigned savedRound=_controlfp(0,0)&_MCW_RC;
    _controlfp(_RC_DOWN,_MCW_RC);Compare(rdp,0,0);Compare(rdp,0,0);
    unsigned beforeRoundChange=geometryBuilds;
    _controlfp(_RC_UP,_MCW_RC);Compare(rdp,0,0);
    require(geometryBuilds==beforeRoundChange+1,"FPSCR rounding-mode change rebuilds geometry");
    _controlfp(savedRound,_MCW_RC);
    std::printf("PASS %u original/projected material cases, all key mutations and repeated hits\n",cases);
    return 0;
}
}
int main(){return Fast::Test();}
