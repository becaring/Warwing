"""Split state reconciliation from per-triangle geometry.

Apply after material math, tracing, cull/emit, shader metadata and texture
bindings. Certify permits a dirty-slot hit only for a restored byte-identical
reload. Other imports use the cold path; primitive depth, diagnostics, area
accounting and vertex packing remain per triangle.
"""
from profile_projections import once
from xbox360_platform.fast3d_triangle_certificate import call_end as _call_end, invalidate_native_calls
from xbox360_platform import fast3d_pipeline_stamps, fast3d_triangle_run

BEGIN='    // PORT: on the RDP, depth *comparison*'
END='    triangleTrace.Mark(SMASH_TRI_DIAGNOSTIC);'


def header(text):
    text='#include <cstring>\nstruct SmashTriangleTrace;\n'+text
    text=once(text,'class Interpreter {',
        '#include "fast3d/triangle_traits.h"\n#include "fast3d/triangle_pipeline.h"\n\nclass Interpreter {')
    return once(text,'    void XboxInvalidateTextureBindings();','''    void XboxInvalidateTextureBindings();
    bool XboxPrepareTrianglePipeline(SmashTriangleTrace& triangleTrace);
    XboxTrianglePipelineKey mXboxPipelineKey;
    unsigned mXboxPipelineCertified;
    XboxTrianglePipelineResult mXboxPipelineResult;''')


def transform(text):
    start=text.index(BEGIN);end=text.index(END,start)
    original=text[start:end]
    for local in ('v_arr','v1->','v2->','v3->','is_rect'):
        if local in original:raise ValueError('Per-triangle dependency entered reconciliation: '+local)
    cold=once(original,'    triangleTrace.Mark(SMASH_TRI_STATE);\n','')
    cold=once(cold,'        return; // Shader compile failed — skip this draw call',
        '        return false; // Shader compile failed — skip this draw call')
    if 'xboxTextureBoundHeight' not in cold or 'const GfxClipParameters& clip_parameters' not in cold:
        raise ValueError('Pipeline projection requires current material and shader metadata projections')
    publish='''    XboxTrianglePipelineResult& p = mXboxPipelineResult;
    p.comb=comb;p.ccId=cc_id;p.tm=tm;
    p.alpha=use_alpha;p.fog=use_fog;p.grayscale=use_grayscale;p.blendColor=use_blend_color;
    p.redirect=redirect_active;p.numInputs=numInputs;p.clip=clip_parameters;
    for(unsigned i=0;i<2;++i) {
        p.usedTextures[i]=usedTextures[i];p.effectiveTile[i]=effective_tile[i];
        // Original dimensions are only initialized for combiner-used slots.
        if(comb->usedTextures[i]) {
            p.width[i]=tex_width[i];p.height[i]=tex_height[i];
            p.boundWidth[i]=tex_width2[i];p.boundHeight[i]=tex_height2[i];
            p.widthFloat[i]=xboxTextureWidth[i];p.heightFloat[i]=xboxTextureHeight[i];
            p.boundWidthFloat[i]=xboxTextureBoundWidth[i];p.boundHeightFloat[i]=xboxTextureBoundHeight[i];
        } else {
            p.width[i]=p.height[i]=p.boundWidth[i]=p.boundHeight[i]=0;
            p.widthFloat[i]=p.heightFloat[i]=p.boundWidthFloat[i]=p.boundHeightFloat[i]=0;
        }
    }
    // Capture the final node sampler values after both slots reconcile: two
    // slots can alias one cache node and update each other's sampler fields.
    mXboxPipelineKey.Capture(*this,p);
    mXboxPipelineCertified=sXboxPipelineMutation;
    return true;
}

'''
    method='''__declspec(noinline) bool Interpreter::XboxPrepareTrianglePipeline(SmashTriangleTrace& triangleTrace) {
    mXboxPipelineKey.valid=false;
// XBOX ORIGINAL RECONCILIATION BEGIN
'''+cold+'// XBOX ORIGINAL RECONCILIATION END\n'+publish
    warm='''    triangleTrace.Mark(SMASH_TRI_STATE);
    if(!XboxPipelineCurrent(*this)) {
        if(!XboxPrepareTrianglePipeline(triangleTrace))return;
    } else {
        // Keep observer phase order on a hit; no native operation is executed.
        triangleTrace.Mark(SMASH_TRI_COMBINER);
        triangleTrace.Mark(SMASH_TRI_TEXTURE);
        triangleTrace.Mark(SMASH_TRI_SHADER);
    }
    const XboxTrianglePipelineResult& xboxPipeline=mXboxPipelineResult;
    ColorCombiner* comb=xboxPipeline.comb;
    const uint64_t cc_id=xboxPipeline.ccId;
    const uint32_t tm=xboxPipeline.tm;
    const bool use_alpha=xboxPipeline.alpha,use_fog=xboxPipeline.fog,use_grayscale=xboxPipeline.grayscale;
    const bool use_blend_color=xboxPipeline.blendColor,redirect_active=xboxPipeline.redirect;
    const uint8_t numInputs=xboxPipeline.numInputs;
    const bool* usedTextures=xboxPipeline.usedTextures;
    const uint32_t* tex_width=xboxPipeline.width;const uint32_t* tex_height=xboxPipeline.height;
    const uint32_t* tex_width2=xboxPipeline.boundWidth;const uint32_t* tex_height2=xboxPipeline.boundHeight;
    const uint32_t* effective_tile=xboxPipeline.effectiveTile;
    const float* xboxTextureWidth=xboxPipeline.widthFloat;const float* xboxTextureHeight=xboxPipeline.heightFloat;
    const float* xboxTextureBoundWidth=xboxPipeline.boundWidthFloat;const float* xboxTextureBoundHeight=xboxPipeline.boundHeightFloat;
    const GfxClipParameters& clip_parameters=xboxPipeline.clip;

'''
    text=text[:start]+warm+text[end:]
    text=once(text,'void Interpreter::GfxSpTri1(',method+'void Interpreter::GfxSpTri1(')
    text=once(text,'void Interpreter::XboxInvalidateTextureBindings() {',
        'void Interpreter::XboxInvalidateTextureBindings() {\n    mXboxPipelineKey.valid=false;')
    text=once(text,'void Interpreter::InvalidateShaderBindings() {',
        'void Interpreter::InvalidateShaderBindings() {\n    mXboxPipelineKey.valid=false;')
    # Port code registers framebuffer mirrors outside the native-call set.
    # A registry change can redirect an identical reload's import, so the
    # reload restoration may only compare against captures made after it.
    for anchor in ('    mFbTextures[b] = FbTextureRange{ b + sizeBytes, fbId, u0, v0, u1, v1 };',
                   '    mFbTextures.erase(reinterpret_cast<uintptr_t>(base));',
                   '    mFbTextures.clear();'):
        text=once(text,anchor,'    mXboxPipelineKey.valid=false;\n'+anchor)
    text=invalidate_native_calls(text,'mXboxPipelineKey.valid=false',minimum=40)
    # BattleShip's extra key inputs (color-image redirect, shader stack) are
    # written only by non-neutral handlers; clip parameters are cached at Init.
    text=fast3d_pipeline_stamps.install(text)
    # Sampled command traces and GBI traces keep one TRI2 per dispatch. Walk
    # bounds are checked before each continuation reads the next command.
    text=once(text,'        if (commandTrace.active) gfx_step<true>(commandTrace);',
        '        if (commandTrace.active) { sXboxTracedDispatch=true; gfx_step<true>(commandTrace); sXboxTracedDispatch=false; }')
    text=once(text,fast3d_triangle_run.HANDLER,'static bool sXboxTracedDispatch=false;'+chr(10)+fast3d_triangle_run.HANDLER)
    return fast3d_triangle_run.install(text,enable='!sXboxTracedDispatch && !sGbiTraceCallback',
        stop='(sDLBoundsCheck && sDLBoundsCheck((uintptr_t)(cmd + 1)) == kDLBoundsWalkedPast)',
        advance=('Smash360_PerfCount(SMASH_COUNT_COMMANDS);',))
