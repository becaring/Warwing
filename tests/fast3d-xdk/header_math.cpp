#include "fast/interpreter.h"
#ifdef SMASH360_TEST_RDP_VALUE_INIT
#include "fast3d/value_init.h"
#endif
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <new>
#include <stdexcept>
static void require(bool value){if(!value)throw std::runtime_error("Fast3D header/math contract failed");}
// Poison the actual RDP allocation, so a zero-filled fresh heap cannot hide a
// missing value-initialization step. This allocator exists only in this test.
static bool poisonRdpAllocation;
static unsigned poisonedRdpAllocations;
void* operator new(size_t size){
    void* result=std::malloc(size?size:1);
    if(!result)throw std::bad_alloc();
    if(poisonRdpAllocation&&size==sizeof(Fast::RDP)){
        std::memset(result,0xA5,size);++poisonedRdpAllocations;
    }
    return result;
}
void operator delete(void* storage)throw(){std::free(storage);}
#if defined(_MSC_VER) && _MSC_VER >= 1900
void operator delete(void* storage,size_t)throw(){std::free(storage);}
#endif
static void checkColor(const Fast::RGBA& value){require(value.r==0&&value.g==0&&value.b==0&&value.a==0);}
static void checkMetadata(const Fast::RawTexMetadata& value){
    require(value.width==0&&value.height==0&&value.h_byte_scale==1&&value.v_pixel_scale==1);
    require(!value.resource&&value.resource.use_count()==0&&value.type==Fast::TextureType::Error);
}
static void checkRdpValueInitialization(){
    poisonRdpAllocation=true;
#ifdef SMASH360_TEST_RDP_VALUE_INIT
    Fast::RDP* value=Shipyard::Fast3D::NewValueInitialized<Fast::RDP>();
#else
    Fast::RDP* value=new Fast::RDP();
#endif
    poisonRdpAllocation=false;
    require(poisonedRdpAllocations==1);
    const Fast::RDP& rdp=*value;
    for(int i=0;i<2;++i){
        require(rdp.palettes[i]==nullptr&&rdp.palette_dram_addr[i]==nullptr&&!rdp.textures_changed[i]);
        for(int j=0;j<256;++j)require(rdp.palette_staging[i][j]==0);
        require(rdp.loaded_texture[i].addr==nullptr&&rdp.loaded_texture[i].orig_size_bytes==0&&
            rdp.loaded_texture[i].size_bytes==0&&rdp.loaded_texture[i].full_image_line_size_bytes==0&&
            rdp.loaded_texture[i].line_size_bytes==0&&rdp.loaded_texture[i].tex_flags==0&&
            !rdp.loaded_texture[i].masked&&!rdp.loaded_texture[i].blended);
        checkMetadata(rdp.loaded_texture[i].raw_tex_metadata);
    }
    require(rdp.texture_to_load.addr==nullptr&&rdp.texture_to_load.siz==0&&
        rdp.texture_to_load.width==0&&rdp.texture_to_load.tex_flags==0);
    checkMetadata(rdp.texture_to_load.raw_tex_metadata);
    for(int i=0;i<8;++i){
        require(rdp.texture_tile[i].fmt==0&&rdp.texture_tile[i].siz==0&&rdp.texture_tile[i].cms==0&&
            rdp.texture_tile[i].cmt==0&&rdp.texture_tile[i].shifts==0&&rdp.texture_tile[i].shiftt==0&&
            rdp.texture_tile[i].masks==0&&rdp.texture_tile[i].maskt==0&&rdp.texture_tile[i].uls==0&&
            rdp.texture_tile[i].ult==0&&rdp.texture_tile[i].lrs==0&&rdp.texture_tile[i].lrt==0&&
            rdp.texture_tile[i].tmem==0&&rdp.texture_tile[i].line_size_bytes==0&&
            rdp.texture_tile[i].palette==0&&rdp.texture_tile[i].tmem_index==0);
    }
    require(rdp.first_tile_index==0&&rdp.other_mode_l==0&&rdp.other_mode_h==0&&
        rdp.combine_mode==0&&!rdp.grayscale&&rdp.prim_lod_fraction==0&&
        rdp.prim_depth_z==0&&rdp.prim_depth_dz==0);
    checkColor(rdp.env_color);checkColor(rdp.prim_color);checkColor(rdp.fog_color);
    checkColor(rdp.blend_color);checkColor(rdp.fill_color);checkColor(rdp.grayscale_color);
    require(rdp.viewport.x==0&&rdp.viewport.y==0&&rdp.viewport.width==0&&rdp.viewport.height==0&&
        rdp.scissor.x==0&&rdp.scissor.y==0&&rdp.scissor.width==0&&rdp.scissor.height==0&&
        !rdp.viewport_or_scissor_changed&&rdp.z_buf_address==nullptr&&rdp.color_image_address==nullptr&&
        rdp.z_buf_address_raw==0&&rdp.color_image_address_raw==0);
    delete value; // Preserve the production's ordinary-delete ownership path.
    std::puts("poisoned real RDP allocation: all fields, nested defaults and ordinary delete passed");
}
int main(){
    Fast::ShaderPermutation permutation=Fast::ShaderPermutation();
    Fast::ShaderPrewarmProgress progress=Fast::ShaderPrewarmProgress();
    require(permutation.shaderId0==0&&permutation.shaderId1==0);
    require(progress.nextIndex==0&&progress.compiled==0&&progress.alreadyCached==0&&progress.failed==0&&progress.skipped==0&&!progress.complete);
    Fast::RenderingState state=Fast::RenderingState();
    require(state.color_write_enabled&&!state.alpha_blend&&!state.decal_mode&&state.depth_test_and_mask==0&&state.mShaderProgram==nullptr);
    for(int i=0;i<SHADER_MAX_TEXTURES;++i)require(state.mTextures[i]==nullptr);
    checkRdpValueInitialization();
    Fast::TextureCacheKey a=Fast::TextureCacheKey(),b=Fast::TextureCacheKey();
    require(a==b);b.maskt=4;require(!(a==b));b=a;b.tile_height=128;require(!(a==b));
    b=a;b.palette_addrs[1]=reinterpret_cast<const uint8_t*>(128);require(!(a==b));
    ColorCombinerKey first={1,2,3},second={1,2,4};require(first<second&&!(first==second));
    float vector[3]={3,4,0};Fast::Interpreter::NormalizeVector(vector);
    float matrix[4][4]={{1,2,3,4},{5,6,7,8},{9,10,11,12},{13,14,15,16}};
    float identity[4][4]={{1,0,0,0},{0,1,0,0},{0,0,1,0},{0,0,0,1}};
    Fast::Interpreter::MatrixMul(matrix,matrix,identity);
    require(matrix[0][0]==1&&matrix[3][3]==16);
    float transformed[3];Fast::Interpreter::TransposedMatrixMul(transformed,vector,matrix);
    for(int i=0;i<3;++i){unsigned bits;std::memcpy(&bits,&vector[i],4);std::printf("vector %08x\n",bits);std::memcpy(&bits,&transformed[i],4);std::printf("transformed %08x\n",bits);}
    uint64_t seed=0x123456789abcdef0ULL,checksum=1469598103934665603ULL;
    for(unsigned i=0;i<4096;++i){
        seed=seed*6364136223846793005ULL+1;
        ColorCombinerKey key={seed&0x00ffffffffffffffULL,(i&1?SHADER_OPT(ALPHA):0)|(i&2?SHADER_OPT(_2CYC):0),0xffff};
        Fast::ColorCombiner comb=Fast::ColorCombiner();
        Fast::Interpreter::GenerateCC(&comb,key);
        checksum=(checksum^comb.shader_id0)*1099511628211ULL;
        checksum=(checksum^comb.shader_id1)*1099511628211ULL;
        for(int cycle=0;cycle<2;++cycle){checksum=(checksum^static_cast<uint64_t>(comb.usedTextures[cycle]))*1099511628211ULL;
            for(int input=0;input<7;++input)checksum=(checksum^comb.shader_input_mapping[cycle][input])*1099511628211ULL;}
    }
    require(std::strcmp(Fast::Interpreter::CCMUXtoStr(4),"G_CCMUX_SHADE")==0);
    require(std::strcmp(Fast::Interpreter::ACMUXtoStr(7),"G_ACMUX_0")==0);
    std::printf("4096 combiner mappings %08x%08x\n",static_cast<unsigned>(checksum>>32),static_cast<unsigned>(checksum));
    std::puts("header defaults, full texture/combiner keys and actual matrix routines passed");
    return 0;
}
