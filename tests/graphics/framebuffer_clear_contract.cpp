// Host contract model executes the actual projected Clear/BeginFramebuffer
// functions. Only SDK operations are modeled; this does not validate GPU pixels.
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <cstdint>
// Diagnostic observer only; this fixture verifies attachment semantics.
enum { SHIPYARD_PERF_RESTORE };
struct ShipyardPerfScope { explicit ShipyardPerfScope(int) {} };
typedef unsigned DWORD;
enum { TRUE=1, E_INVALIDARG=1, D3DCLEAR_TARGET=1, D3DCLEAR_ZBUFFER=2,
       D3DCLEAR_STENCIL=4, D3DRS_MULTISAMPLEANTIALIAS=0, D3DRS_MULTISAMPLEMASK=1 };
struct D3DVIEWPORT9 {};
struct D3DVECTOR4 { float x,y,z,w; };
struct Framebuffer {
    int *color, *depth, *image, *color_samples[4], *depth_samples[4];
    unsigned width,height,samples;
    bool stored,depth_stored,dirty;
    std::vector<int> tiles;
};
std::vector<Framebuffer> buffers(1);
int active_fb=0;
bool live_framebuffer=false;
unsigned tiling_draw_bytes=0;
unsigned framebuffer_clear_count=0,framebuffer_restore_avoided=0,framebuffer_depth_restore_avoided=0;
bool framebuffer_clear_reuse_disabled=false;
unsigned restore_draws=0,depth_reads=0;
int gpu_color[4],gpu_depth[4];
void InvalidateNativeState() {}
void SetTileConstants() {}
void Shipyard_Check(int result,const char*) { if(result)std::abort(); }
void Shipyard_Fatal(const char*,int) { std::abort(); }
void ClearFramebufferTargets(DWORD flags) {
    for(unsigned s=0;s<buffers[0].samples;++s) {
        if(flags&D3DCLEAR_TARGET)gpu_color[s]=0;
        if(flags&D3DCLEAR_ZBUFFER)gpu_depth[s]=1;
    }
}
struct Device {
    void GetViewport(D3DVIEWPORT9*) {}
    int SetRenderTarget(int,int*) { return 0; }
    int SetDepthStencilSurface(int*) { return 0; }
    void SetViewport(D3DVIEWPORT9*) {}
    void SetRenderState(int,unsigned) {}
    void BeginTiling(int,DWORD,int*,D3DVECTOR4*,int,int) {
        ClearFramebufferTargets(D3DCLEAR_TARGET|D3DCLEAR_ZBUFFER);
    }
} device,*xenos_device=&device;
void RestoreQuad(int* color,int* depth,unsigned,unsigned,DWORD mask) {
    ++restore_draws;
    if(depth)++depth_reads;
    for(unsigned s=0;s<buffers[0].samples;++s)if(mask&(1u<<s)) {
        gpu_color[s]=*color;
        if(depth)gpu_depth[s]=*depth;
    }
}
#include "actual_framebuffer_clear.inc"
int main() {
    unsigned cases=0,failed=0,wasted_draws=0,wasted_depth_reads=0;
    for(unsigned samples=1;samples<=4;samples*=2)
    for(int tiled=0;tiled<2;++tiled)
    for(int has_depth=0;has_depth<2;++has_depth)
    for(int live=0;live<2;++live)
    for(int color=0;color<2;++color)
    for(int depth=0;depth<2;++depth) {
        int saved_color[4]={11,12,13,14},saved_depth[4]={21,22,23,24};
        Framebuffer& b=buffers[0];
        b.color=saved_color;b.depth=has_depth?saved_depth:NULL;b.image=saved_color;
        b.width=1280;b.height=720;b.samples=samples;b.tiles.assign(tiled?2:1,0);
        b.stored=true;b.depth_stored=has_depth!=0;b.dirty=false;
        for(unsigned s=0;s<samples;++s) {
            b.color_samples[s]=&saved_color[s];b.depth_samples[s]=&saved_depth[s];
            gpu_color[s]=live?saved_color[s]:-99;gpu_depth[s]=live?saved_depth[s]:-99;
        }
        live_framebuffer=live!=0;restore_draws=depth_reads=0;
        Clear(color!=0,depth!=0);
        if(!color&&!depth) { if(restore_draws)++failed; continue; }
        ++cases;
        for(unsigned s=0;s<samples;++s) {
            if(gpu_color[s]!=(color?0:saved_color[s]))++failed;
            if(has_depth&&gpu_depth[s]!=(depth?1:saved_depth[s]))++failed;
        }
        if(!live&&color&&(depth||!has_depth))wasted_draws+=restore_draws;
        if(!live&&depth&&has_depth)wasted_depth_reads+=depth_reads;
    }
    std::printf("clear contract: %u cases, %u pixel-model errors, %u overwritten restore draws, %u overwritten depth reads\n",
        cases,failed,wasted_draws,wasted_depth_reads);
    return failed||wasted_draws||wasted_depth_reads?1:0;
}
