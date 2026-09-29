#include "fast/interpreter.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stack>
namespace Fast {
// CACHE_DECLARATIONS
struct Owner {
    RDP rdp; RSP rsp; RDP* mRdp;RSP* mRsp;
    RenderingState mRenderingState;
    ColorCombiner comb;
    std::stack<int16_t> mShaderStack;
    GfxClipParameters mXboxClipParameters;
    void* mRapi;
    TextureCacheNode nodes[6];
    Owner():rdp(),rsp(),mRdp(&rdp),mRsp(&rsp),mRenderingState(),comb(),mRapi(this) {
        comb.usedTextures[0]=comb.usedTextures[1]=true;
        rdp.texture_tile[1].tmem_index=1;
        mXboxClipParameters.z_is_from_0_to_1=true;mXboxClipParameters.invertY=false;
        for(unsigned i=0;i<6;++i){mRenderingState.mTextures[i]=&nodes[i];nodes[i].second.linear_filter=false;nodes[i].second.cms=nodes[i].second.cmt=0;}
    }
    bool RdpColorImageIsZBuffer() const {
        if(mRdp->color_image_address!=NULL && mRdp->color_image_address==mRdp->z_buf_address)return true;
        return mRdp->color_image_address_raw!=0 && mRdp->color_image_address_raw==mRdp->z_buf_address_raw;
    }
};
static unsigned checked;
static void Require(bool value,const char* message){++checked;if(!value){std::fprintf(stderr,"FAIL %s\n",message);std::exit(1);}}
}
int main() {
    using namespace Fast;
    Owner owner;XboxTrianglePipelineKey key;XboxTrianglePipelineResult result={};result.comb=&owner.comb;
    key.Capture(owner,result);
    Require(key.Matches(owner),"unchanged real RDP/render state still reconciles");
#define CHANGE(field,expression) {auto old=(field);(field)=(expression);Require(!key.Matches(owner),#field " absent from key");(field)=old;Require(key.Matches(owner),#field " restoration mismatch");}
    for(unsigned bit=0;bit<64;++bit)CHANGE(owner.rdp.combine_mode,uint64_t(1)<<bit);
    for(unsigned bit=0;bit<32;++bit) {
        CHANGE(owner.rdp.other_mode_l,uint32_t(1)<<bit);
        CHANGE(owner.rdp.other_mode_h,uint32_t(1)<<bit);
    }
    CHANGE(owner.rdp.grayscale,true);
    CHANGE(owner.rsp.geometry_mode,(uint32_t)G_ZBUFFER);
    CHANGE(owner.rdp.first_tile_index,1);
    CHANGE(owner.mRapi,(void*)NULL);
    CHANGE(owner.mXboxClipParameters.z_is_from_0_to_1,false);
    CHANGE(owner.mXboxClipParameters.invertY,true);
    CHANGE(owner.rdp.viewport_or_scissor_changed,true);
    for(unsigned i=0;i<2;++i) {
        // A byte-identical reload restores (SoH 4.0.5 rule): every import key
        // and the bound node are unchanged. Any byte of either TMEM entry or
        // palette identity still reconciles, and Certify clears the used
        // slot's flag exactly as upstream's import would.
        owner.rdp.textures_changed[i]=true;
        Require(key.Matches(owner),"identical reloaded texture not restored");
        {unsigned char* image=(unsigned char*)&owner.rdp.loaded_texture[0];
         for(unsigned j=0;j<sizeof(owner.rdp.loaded_texture);++j){
             image[j]^=1;Require(!key.Matches(owner),"reloaded texture byte absent from key");image[j]^=1;}}
        for(unsigned half=0;half<2;++half){
            const uint8_t* saved=owner.rdp.palette_dram_addr[half];
            owner.rdp.palette_dram_addr[half]=(const uint8_t*)&owner;
            Require(!key.Matches(owner),"reloaded palette identity absent from key");
            owner.rdp.palette_dram_addr[half]=saved;}
        Require(key.Certify(owner)&&!owner.rdp.textures_changed[i],"certified reload kept the used dirty flag");
        CHANGE(owner.rdp.loaded_texture[i].masked,true);
        CHANGE(owner.rdp.loaded_texture[i].blended,true);
        CHANGE(owner.rdp.loaded_texture[i].size_bytes,37u);
        CHANGE(owner.rdp.loaded_texture[i].line_size_bytes,5u);
        CHANGE(owner.rdp.loaded_texture[i].full_image_line_size_bytes,7u);
        CHANGE(owner.rdp.loaded_texture[i].orig_size_bytes,39u);
        CHANGE(owner.nodes[i].second.linear_filter,true);
        CHANGE(owner.nodes[i].second.cms,2);
        CHANGE(owner.nodes[i].second.cmt,2);
        unsigned char* tile=(unsigned char*)&owner.rdp.texture_tile[i];
        for(unsigned j=0;j<sizeof(owner.rdp.texture_tile[i]);++j) {
            tile[j]^=1;Require(!key.Matches(owner),"active tile byte absent from key");tile[j]^=1;
        }
    }
    unsigned char* rendering=(unsigned char*)&owner.mRenderingState;
    for(unsigned i=0;i<sizeof(owner.mRenderingState);++i) {
        rendering[i]^=1;Require(!key.Matches(owner),"public rendering-state byte absent from key");rendering[i]^=1;
    }
    owner.mShaderStack.push(4);Require(!key.Matches(owner),"custom shader push not observed");
    key.Capture(owner,result);Require(key.Matches(owner),"custom shader cannot certify");
    owner.mShaderStack.top()=5;Require(!key.Matches(owner),"custom shader value not observed");
    owner.mShaderStack.pop();key.Capture(owner,result);
    owner.rdp.color_image_address_raw=owner.rdp.z_buf_address_raw=123;
    Require(!key.Matches(owner),"raw color-to-depth redirect not observed");
    owner.rdp.color_image_address_raw=owner.rdp.z_buf_address_raw=0;
    owner.rdp.color_image_address=owner.rdp.z_buf_address=&owner;
    Require(!key.Matches(owner),"resolved color-to-depth redirect not observed");
    owner.rdp.color_image_address=owner.rdp.z_buf_address=NULL;
    // These are consumed after reconciliation and must remain live.
    owner.rdp.prim_depth_z=456;owner.rdp.prim_color.r=42;owner.rdp.fog_color.b=91;
    owner.rsp.loaded_vertices[3].x=9.0f;
    Require(key.Matches(owner),"live primitive/vertex work incorrectly part of reconciliation");
    // Base mip collapse: both used slots reference first_tile when it is >=2.
    owner.rdp.first_tile_index=7;key.Capture(owner,result);Require(key.Matches(owner),"base mip tile collapse changed");
    owner.rdp.texture_tile[0].uls=99.0f;Require(key.Matches(owner),"unused tile affected key");
    CHANGE(owner.rdp.texture_tile[7].uls,3.0f);
    owner.rdp.texture_tile[7].tmem_index=1;key.Capture(owner,result);
    CHANGE(owner.rdp.loaded_texture[1].line_size_bytes,72u);
    owner.rdp.first_tile_index=255;key.Capture(owner,result);Require(!key.valid,"invalid active tile certified");
    owner.rdp.first_tile_index=0;owner.rdp.texture_tile[0].tmem_index=2;key.Capture(owner,result);Require(!key.valid,"invalid TMEM index certified");
    owner.rdp.texture_tile[0].tmem_index=0;
    owner.rdp.texture_tile[0].uls=0.0f;
    owner.comb.usedTextures[1]=false;owner.rdp.textures_changed[1]=true;
    key.Capture(owner,result);Require(key.Matches(owner),"unused dirty slot blocked reconciliation reuse");
    Require(owner.rdp.textures_changed[1],"unused dirty flag was cleared");
    // A changed combiner identity must reconcile; once it uses slot one,
    // certification cannot succeed until that slot's actual import clears it.
    owner.rdp.combine_mode^=1;owner.comb.usedTextures[1]=true;
    Require(!key.Matches(owner),"combiner usage transition reused old result");
    key.Capture(owner,result);Require(!key.valid,"required dirty import was skipped");
    owner.rdp.textures_changed[1]=false;key.Capture(owner,result);Require(key.Matches(owner),"completed original import could not certify");
    for(unsigned bits=0x7f800000;bits<=0x7f800002;++bits) {
        std::memcpy(&owner.rdp.texture_tile[0].uls,&bits,4);key.Capture(owner,result);
        Require(!key.valid,"nonfinite tile arithmetic was certified");
    }
    std::puts("PASS real RDP/render-state pipeline key mutation coverage");
    std::printf("%u checks\n",checked);
}
