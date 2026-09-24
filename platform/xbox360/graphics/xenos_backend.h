#pragma once
#include "fast/backends/gfx_rendering_api.h"
#include "fast/backends/gfx_window_manager_api.h"
#include "presentation/xenos_surface.h"

namespace Fast {
void ReportNativeBindingConstants();
class GfxRenderingAPIXenos : public GfxRenderingAPI {
public:
    virtual ~GfxRenderingAPIXenos();
    const char* GetName();
    int GetMaxTextureSize();
    GfxClipParameters GetClipParameters();
    void UnloadShader(ShaderProgram*);
    void LoadShader(ShaderProgram*);
    ShaderProgramKey MakeShaderProgramKey(uint64_t, uint64_t) const;
    ShaderProgram* CreateAndLoadNewShader(const ShaderProgramKey&);
    ShaderProgram* LookupShader(const ShaderProgramKey&);
    void ShaderGetInfo(ShaderProgram*, uint8_t*, bool[2]);
    uint32_t NewTexture();
    void SelectTexture(int, uint32_t);
    void UploadTexture(const uint8_t*, uint32_t, uint32_t);
    void SetSamplerParameters(int, bool, uint32_t, uint32_t);
    void SetDepthTestAndMask(bool, bool);
    void SetZmodeDecal(bool);
    void SetViewport(int, int, int, int);
    void SetScissor(int, int, int, int);
    void SetUseAlpha(bool);
    void DrawTriangles(float[], size_t, size_t);
    void Init();
    void OnResize();
    void StartFrame();
    void EndFrame();
    void FinishRender();
    int CreateFramebuffer();
    void DestroyFramebuffer(int);
    void UpdateFramebufferParameters(int,uint32_t,uint32_t,uint32_t,bool,bool,bool,bool);
    void StartDrawToFramebuffer(int,float);
    void CopyFramebuffer(int,int,int,int,int,int,int,int,int,int);
    void ClearFramebuffer(bool,bool);
    void SetColorWriteMask(bool);
    void ClearColorRegion(float,float,float,float);
    void ReadFramebufferToCPU(int,uint32_t,uint32_t,uint16_t*);
    void ResolveMSAAColorBuffer(int,int);
    std::unordered_map<std::pair<float,float>,uint16_t,hash_pair_ff>
        GetPixelDepth(int,const std::set<std::pair<float,float> >&);
    void* GetFramebufferTextureId(int);
    void SelectTextureFb(int);
    bool FbNeedsSampleVFlip(int);
    void DeleteTexture(uint32_t);
    void SetTextureFilter(FilteringMode);
    FilteringMode GetTextureFilter();
    void SetSrgbMode();
    ImTextureID GetTextureById(int);
};
class GfxWindowBackendXenos : public GfxWindowBackend {
public:
    GfxWindowBackendXenos();
    void Init(const char*,const char*,bool,uint32_t,uint32_t,int32_t,int32_t);
    void Close();
    void SetKeyboardCallbacks(bool (*)(int),bool (*)(int),void (*)());
    void SetMouseCallbacks(bool (*)(int),bool (*)(int));
    void SetFullscreenChangedCallback(void (*)(bool));
    void SetFullscreen(bool);
    void GetActiveWindowRefreshRate(uint32_t*);
    void SetCursorVisibility(bool);
    void SetMousePos(int32_t,int32_t);
    void GetMousePos(int32_t*,int32_t*);
    void GetMouseDelta(int32_t*,int32_t*);
    void GetMouseWheel(float*,float*);
    bool GetMouseState(uint32_t);
    void SetMouseCapture(bool);
    bool IsMouseCaptured();
    void GetDimensions(uint32_t*,uint32_t*,int32_t*,int32_t*);
    void HandleEvents();
    bool IsFrameReady();
    void SwapBuffersBegin();
    void SwapBuffersEnd();
    double GetTime();
    int GetTargetFps();
    void SetTargetFps(int);
    void SetMaxFrameLatency(int);
    const char* GetKeyName(int);
    bool CanDisableVsync();
    bool IsRunning();
    void Destroy();
    bool IsFullscreen();
private:
    void (*mAllKeysUp)();
    Shipyard::XenosPresentationSurface mSurface;
};
}
