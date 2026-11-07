#include "xenos_backend.h"
#include "xenos/core.h"
#include "interop.h"
#include "services.h"
#include "xenos/shader_cache.h"
#include "xenos/shader_pack_program.h"
#include "../runtime/perf_trace.h"

namespace Fast {
void InitializeNativeDisplay(){ShipyardXenos::InitializeDisplay();}
HRESULT PresentNativeStartupUI(){return ShipyardXenos::PresentStartupUI();}
void BeginNativeGuiDraw(){ShipyardXenos::BeginGuiDraw();}
void InvalidateNativeGuiState(){ShipyardXenos::InvalidateGuiState();}
void ShutdownNativeDisplay(){ShipyardXenos::Shutdown();}
bool ReadPresentedFrameRGBA(std::vector<uint8_t>& pixels,uint32_t& width,uint32_t& height){
    return ShipyardXenos::ReadPresentedFrameRGBA(pixels,width,height);
}
GfxRenderingAPIXenos::~GfxRenderingAPIXenos(){ShipyardXenos::Shutdown();}
const char* GfxRenderingAPIXenos::GetName(){return "Xenos";}
int GfxRenderingAPIXenos::GetMaxTextureSize(){return 4096;}
GfxClipParameters GfxRenderingAPIXenos::GetClipParameters(){return ShipyardXenos::ClipParameters();}
void GfxRenderingAPIXenos::UnloadShader(ShaderProgram* p){ShipyardXenos::UnloadShader(p);}
void GfxRenderingAPIXenos::LoadShader(ShaderProgram* p){ShipyardXenos::LoadShader(p);}
ShaderProgramKey GfxRenderingAPIXenos::MakeShaderProgramKey(uint64_t a,uint64_t b) const {
    ShaderProgramKey key;key.shaderId0=a;key.shaderId1=b;
    key.filteringMode=ShipyardXenos::GetTextureFilter();key.srgbMode=mSrgbMode;
    return key;
}
ShaderProgram* GfxRenderingAPIXenos::CreateAndLoadNewShader(const ShaderProgramKey& key){return ShipyardXenos::CreateShader(key);}
ShaderProgram* GfxRenderingAPIXenos::LookupShader(const ShaderProgramKey& key){return ShipyardXenos::LookupShader(key);}
void GfxRenderingAPIXenos::ShaderGetInfo(ShaderProgram* p,uint8_t* n,bool used[2]){ShipyardXenos::ShaderInfo(p,n,used);}
uint32_t GfxRenderingAPIXenos::NewTexture(){return ShipyardXenos::NewTexture();}
void GfxRenderingAPIXenos::SelectTexture(int slot,uint32_t id){ShipyardXenos::SelectTexture(slot,id);}
void GfxRenderingAPIXenos::UploadTexture(const uint8_t* p,uint32_t w,uint32_t h){ShipyardXenos::UploadTexture(p,w,h);}
void GfxRenderingAPIXenos::SetSamplerParameters(int slot,bool linear,uint32_t s,uint32_t t){ShipyardXenos::SetSamplerParameters(slot,linear,s,t);}
void GfxRenderingAPIXenos::SetDepthTestAndMask(bool test,bool write){ShipyardXenos::SetDepthTestAndMask(test,write);}
void GfxRenderingAPIXenos::SetZmodeDecal(bool decal){ShipyardXenos::SetZmodeDecal(decal);}
void GfxRenderingAPIXenos::SetViewport(int x,int y,int w,int h){ShipyardXenos::SetViewport(x,y,w,h);}
void GfxRenderingAPIXenos::SetScissor(int x,int y,int w,int h){ShipyardXenos::SetScissor(x,y,w,h);}
void GfxRenderingAPIXenos::SetUseAlpha(bool alpha){ShipyardXenos::SetUseAlpha(alpha);}
void GfxRenderingAPIXenos::DrawTriangles(float v[],size_t count,size_t tris){ShipyardXenos::DrawTriangles(v,count,tris);}
void GfxRenderingAPIXenos::Init(){
    // tools/build_shader_pack.py output, each program verified against this build on first use.
    Shipyard::Xenos::ConfigureShaderPack("game:\\shaders\\smash360.shaderpack");
    const Shipyard::Xenos::ShaderCacheConfig config={"smashsave:\\smash360-shaders.cache",2,Smash360_QueueShaderCacheWrite};
    if(!Shipyard::Xenos::ConfigureShaderCache(config))Smash360_Fatal("shader cache configuration",E_UNEXPECTED);
    const ShipyardXenos::ShaderCacheOps cache={Shipyard::Xenos::LoadShaderCode,Shipyard::Xenos::StoreShaderCode,
                                               Shipyard::Xenos::PackedFast3DProgram};
    ShipyardXenos::SetShaderCache(&cache);
    ShipyardXenos::Init();Smash360_InitializeGuiForXenos();
}
void GfxRenderingAPIXenos::OnResize(){ShipyardXenos::Resize();}
void GfxRenderingAPIXenos::StartFrame(){ShipyardXenos::StartFrame();}
void GfxRenderingAPIXenos::EndFrame(){ShipyardXenos::EndFrame();}
void GfxRenderingAPIXenos::FinishRender(){ShipyardXenos::FinishRender();}
int GfxRenderingAPIXenos::CreateFramebuffer(){return ShipyardXenos::CreateFramebuffer();}
void GfxRenderingAPIXenos::DestroyFramebuffer(int id){ShipyardXenos::DestroyFramebuffer(id);}
void GfxRenderingAPIXenos::UpdateFramebufferParameters(int id,uint32_t w,uint32_t h,uint32_t msaa,
                                                       bool flip,bool target,bool depth,bool read){
    ShipyardXenos::UpdateFramebuffer(id,w,h,msaa,flip,target,depth,read);
}
void GfxRenderingAPIXenos::StartDrawToFramebuffer(int id,float noise){ShipyardXenos::StartDrawToFramebuffer(id,noise);}
void GfxRenderingAPIXenos::CopyFramebuffer(int dst,int src,int sx0,int sy0,int sx1,int sy1,int dx0,int dy0,int dx1,int dy1){
    ShipyardXenos::CopyFramebuffer(dst,src,sx0,sy0,sx1,sy1,dx0,dy0,dx1,dy1);
}
void GfxRenderingAPIXenos::ClearFramebuffer(bool color,bool depth){ShipyardXenos::ClearFramebuffer(color,depth);}
void GfxRenderingAPIXenos::SetColorWriteMask(bool enabled){ShipyardXenos::SetColorWriteMask(enabled);}
void GfxRenderingAPIXenos::ClearColorRegion(float x0,float y0,float x1,float y1){ShipyardXenos::ClearColorRegion(x0,y0,x1,y1);}
void GfxRenderingAPIXenos::ReadFramebufferToCPU(int id,uint32_t w,uint32_t h,uint16_t* p){ShipyardXenos::ReadFramebufferToCPU(id,w,h,p);}
void GfxRenderingAPIXenos::ResolveMSAAColorBuffer(int dst,int src){ShipyardXenos::ResolveMSAAColorBuffer(dst,src);}
std::unordered_map<std::pair<float,float>,uint16_t,hash_pair_ff>
GfxRenderingAPIXenos::GetPixelDepth(int id,const std::set<std::pair<float,float> >& xy){
    return ShipyardXenos::GetPixelDepth(id,xy);
}
void* GfxRenderingAPIXenos::GetFramebufferTextureId(int id){return ShipyardXenos::GetFramebufferTextureId(id);}
void GfxRenderingAPIXenos::SelectTextureFb(int id){ShipyardXenos::SelectTextureFb(id);}
bool GfxRenderingAPIXenos::FbNeedsSampleVFlip(int id){return ShipyardXenos::FbNeedsSampleVFlip(id);}
void GfxRenderingAPIXenos::DeleteTexture(uint32_t id){ShipyardXenos::DeleteTexture(id);}
// Like upstream DX11: cached uploads and the bound shader carry the old filter.
extern "C" void gfx_texture_cache_clear();
void GfxRenderingAPIXenos::SetTextureFilter(FilteringMode mode){
    ShipyardXenos::SetTextureFilter(mode);gfx_texture_cache_clear();
    if(ShipyardXenos::CurrentShader())LoadShader(ShipyardXenos::CurrentShader());
}
FilteringMode GfxRenderingAPIXenos::GetTextureFilter(){return ShipyardXenos::GetTextureFilter();}
void GfxRenderingAPIXenos::SetSrgbMode(){mSrgbMode=true;}
ImTextureID GfxRenderingAPIXenos::GetTextureById(int id){return ShipyardXenos::GetTextureById(id);}
void CaptureNativePerf(Smash360NativePerf* n) {
    ShipyardXenos::NativeCounters counters;
    ShipyardXenos::CaptureAndResetCounters(&counters);
    n->samplerAttempted=counters.samplerAttempted;
    n->samplerWritten=counters.samplerWritten;
    n->samplerSuppressed=counters.samplerSuppressed;
    n->constantsAttempted=counters.constantsAttempted;
    n->constantsWritten=counters.constantsWritten;
    n->constantsSuppressed=counters.constantsSuppressed;
    n->bindingAttempted=counters.bindingAttempted;
    n->bindingWritten=counters.bindingWritten;
    n->bindingSuppressed=counters.bindingSuppressed;
    n->uploadRequests=counters.uploadRequests;
    n->uploadReused=counters.uploadReused;
    n->uploadSavedBytes=counters.uploadSavedBytes;
    n->clears=counters.clears;
    n->restoresAvoided=counters.restoresAvoided;
    n->depthRestoresAvoided=counters.depthRestoresAvoided;
    n->pendingTextures=counters.pendingTextures;
    n->pendingBytes=counters.pendingBytes;
    n->width=counters.width;
    n->height=counters.height;
    n->samples=counters.samples;
    n->tiles=counters.tiles;
}
void ReportNativeBindingConstants() {
    ShipyardXenos::NativeCounters counters;
    ShipyardXenos::CaptureAndResetCounters(&counters);
    Smash360_Log("RENDER binding_constants attempted=%u written=%u suppressed=%u",
        counters.bindingAttempted,counters.bindingWritten,counters.bindingSuppressed);
    Smash360_Log("RENDER clears=%u restore_draws_avoided=%u depth_sample_restores_avoided=%u",
        counters.clears,counters.restoresAvoided,counters.depthRestoresAvoided);
}
}
