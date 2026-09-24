#include "xenos_backend.h"
// Real allocations force the compiler to verify both exact current interfaces
// are concrete. This is an object probe, never an application entry point.
Fast::GfxRenderingAPI* GraphicsContractCreate(){return new Fast::GfxRenderingAPIXenos();}
Fast::GfxWindowBackend* WindowContractCreate(){return new Fast::GfxWindowBackendXenos();}
