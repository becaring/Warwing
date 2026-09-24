#include "services.h"
#include "xenos_backend.h"
#include "native_display.h"
#include "../runtime/perf_trace.h"
#include "../runtime/triangle_trace.h"
#include "../runtime/command_trace.h"
#include "../runtime/frame_workload.h"
namespace Fast {
extern IDirect3DDevice9* xenos_device;
namespace {
Smash360WindowInput input={};
// Same logic/render/present split used by SoH's profile window, observed at
// BattleShip's existing window boundaries without changing its scheduler.
double frameReadyAt=0,lastPresentAt=0,profileStart=0;
double profileLogic=0,profileRender=0,profilePresent=0;
unsigned profileFrames=0;
unsigned frameCommandStart=0;
SmashFrameWorkload frameWorkload={};
}
GfxWindowBackendXenos::GfxWindowBackendXenos():mAllKeysUp(NULL) {
    mOnFullscreenChanged=NULL;mOnKeyDown=NULL;mOnKeyUp=NULL;
    mOnMouseButtonDown=NULL;mOnMouseButtonUp=NULL;mFullScreen=true;
}
void GfxWindowBackendXenos::Init(const char*,const char*,bool,uint32_t,uint32_t,int32_t,int32_t){
    InitializeNativeDisplay();
    Smash360_Check(mSurface.Attach(xenos_device),"display mode");
    mIsRunning=true;input.running=true;Smash360_InitPerf();
}
void GfxWindowBackendXenos::Close(){input.running=false;mIsRunning=false;}
void GfxWindowBackendXenos::SetKeyboardCallbacks(bool (*down)(int),bool (*up)(int),void (*all)()){mOnKeyDown=down;mOnKeyUp=up;mAllKeysUp=all;}
void GfxWindowBackendXenos::SetMouseCallbacks(bool (*down)(int),bool (*up)(int)){mOnMouseButtonDown=down;mOnMouseButtonUp=up;}
void GfxWindowBackendXenos::SetFullscreenChangedCallback(void (*callback)(bool)){mOnFullscreenChanged=callback;if(callback)callback(true);}
void GfxWindowBackendXenos::SetFullscreen(bool){if(mOnFullscreenChanged)mOnFullscreenChanged(true);}
void GfxWindowBackendXenos::GetActiveWindowRefreshRate(uint32_t* hz){*hz=mSurface.Refresh();}
void GfxWindowBackendXenos::SetCursorVisibility(bool visible){Smash360_SetPointerVisible(visible);}
void GfxWindowBackendXenos::SetMousePos(int32_t x,int32_t y){Smash360_SetPointerPosition(x,y);}
void GfxWindowBackendXenos::GetMousePos(int32_t* x,int32_t* y){*x=input.x;*y=input.y;}
void GfxWindowBackendXenos::GetMouseDelta(int32_t* x,int32_t* y){*x=input.deltaX;*y=input.deltaY;}
void GfxWindowBackendXenos::GetMouseWheel(float* x,float* y){*x=input.wheelX;*y=input.wheelY;}
bool GfxWindowBackendXenos::GetMouseState(uint32_t btn){return btn<32 && (input.buttons&(1u<<btn))!=0;}
void GfxWindowBackendXenos::SetMouseCapture(bool capture){Smash360_SetPointerCaptured(capture);}
bool GfxWindowBackendXenos::IsMouseCaptured(){return input.captured;}
void GfxWindowBackendXenos::GetDimensions(uint32_t* w,uint32_t* h,int32_t* x,int32_t* y){*w=1280;*h=720;*x=*y=0;}
void GfxWindowBackendXenos::HandleEvents(){Smash360_PollWindowInput(&input,mOnKeyDown,mOnKeyUp,mAllKeysUp,mOnMouseButtonDown,mOnMouseButtonUp);mIsRunning=input.running;}
bool GfxWindowBackendXenos::IsFrameReady(){
    if(!mIsRunning)return false;
    frameReadyAt=Smash360_Time();
    if(!profileStart) {profileStart=frameReadyAt;Smash360_ResetPerf();}
    if(lastPresentAt)profileLogic+=frameReadyAt-lastPresentAt;
    if(smash360_command_trace)frameCommandStart=smash360_command_samples.calls;
    bool ready=false;
    Smash360_Check(mSurface.Prepare(Smash360_Time,&ready),"presentation interval");
    if(!ready)return false;
    return true;
}
void GfxWindowBackendXenos::SwapBuffersBegin(){
    const double begin=Smash360_Time();
    Smash360_Check(mSurface.Present(),"Present");
    const double end=Smash360_Time();
    if(!profileStart)profileStart=frameReadyAt;
    profileRender+=begin-frameReadyAt;profilePresent+=end-begin;
    if(smash360_command_trace && lastPresentAt) {
        frameWorkload.Add(smash360_command_samples.calls-frameCommandStart,
            end-lastPresentAt,frameReadyAt-lastPresentAt,begin-frameReadyAt,end-begin);
    }
    lastPresentAt=end;++profileFrames;
    if(end-profileStart>=5) {
        Smash360_Log("FRAME timing frames=%u elapsed=%.3f logic_ms=%.3f render_ms=%.3f present_ms=%.3f",
            profileFrames,end-profileStart,1000*profileLogic/profileFrames,
            1000*profileRender/profileFrames,1000*profilePresent/profileFrames);
        Smash360_ReportPerf(profileFrames,end-profileStart,profileLogic,profileRender,profilePresent);
        if(smash360_command_trace) {
            for(unsigned i=0;i<SmashFrameWorkload::Count;++i) {
                const SmashFrameWorkload::Band& band=frameWorkload.bands[i];
                if(!band.frames)continue;
                Smash360_Log("FRAME_WORKLOAD commands_min=%u commands_max=%u frames=%u fps=%.2f logic_ms=%.3f render_ms=%.3f present_ms=%.3f",
                    i*SmashFrameWorkload::Width,
                    i+1==SmashFrameWorkload::Count?~0u:(i+1)*SmashFrameWorkload::Width-1,
                    band.frames,band.elapsed>0?band.frames/band.elapsed:0,
                    1000*band.logic/band.frames,1000*band.render/band.frames,1000*band.present/band.frames);
            }
            frameWorkload.Reset();
        }
        Smash360_ReportTriangleTrace(profileFrames);
        if(!smash360_perf_enabled)ReportNativeBindingConstants();
        profileStart=end;profileFrames=0;profileLogic=profileRender=profilePresent=0;
    }
}
void GfxWindowBackendXenos::SwapBuffersEnd(){}
double GfxWindowBackendXenos::GetTime(){return Smash360_Time();}
int GfxWindowBackendXenos::GetTargetFps(){return mTargetFps;}
void GfxWindowBackendXenos::SetTargetFps(int fps){if(fps<=0)Smash360_Fatal("presentation rate",E_INVALIDARG);mSurface.SetRate(fps);mTargetFps=fps;}
void GfxWindowBackendXenos::SetMaxFrameLatency(int frames){Smash360_Check(mSurface.SetMaxFrameLatency(frames),"frame latency");}
const char* GfxWindowBackendXenos::GetKeyName(int scan){return Smash360_KeyName(scan);}
bool GfxWindowBackendXenos::CanDisableVsync(){return false;}
bool GfxWindowBackendXenos::IsRunning(){return mIsRunning;}
void GfxWindowBackendXenos::Destroy(){Close();}
bool GfxWindowBackendXenos::IsFullscreen(){return true;}
}
