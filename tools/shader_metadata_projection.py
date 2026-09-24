"""Reuse immutable shader metadata and Xbox clip parameters, as in SoH360.

Donor gfx_pc.cpp stores num_inputs/program_textures per ColorCombiner clamp
variant and queries native_clip_parameters in gfx_init. Keep BattleShip's
shader lookup/failure, flush, bind and alpha sequence intact. Metadata is read
through its existing rendering API, not reconstructed from combiner bits.
"""
from profile_projections import once


def header(text):
    text='#include "fast3d/shader_metadata_cache.h"\n'+text
    text=once(text,'    struct ShaderProgram* prg[16];','''    struct ShaderProgram* prg[16];
    // The consumer owns the combiner lifetime and variant mapping.
    Shipyard::Fast3D::ShaderMetadataCache<16> xboxShaderMetadata;''')
    return once(text,'    GfxRenderingAPI* mRapi = nullptr;','''    GfxRenderingAPI* mRapi = nullptr;
    GfxClipParameters mXboxClipParameters;''')


def transform(text):
    text=once(text,'    mRapi->Init();','''    mRapi->Init();
    // Xenos ClipParameters is constant for the backend lifetime. Refresh at
    // every Init, including reuse of the same Interpreter/backend addresses.
    mXboxClipParameters = mRapi->GetClipParameters();
    for (auto& entry : mColorCombinerPool) {
        entry.second.xboxShaderMetadata.Invalidate();
    }''')
    old='''    mRapi->ShaderGetInfo(prg, &numInputs, usedTextures);

    struct GfxClipParameters clip_parameters = mRapi->GetClipParameters();'''
    new='''    // Preserve all state transitions above. Only immutable API results are
    // reused; failures returned before reaching this point, as upstream does.
    Shipyard::Fast3D::ShaderMetadata xboxMetadata;
    if (!comb->xboxShaderMetadata.Lookup(tm, mRapi, prg, xboxMetadata)) {
        mRapi->ShaderGetInfo(prg, &xboxMetadata.numInputs, xboxMetadata.usedTextures);
        comb->xboxShaderMetadata.Store(tm, mRapi, prg, xboxMetadata);
    }
    numInputs = xboxMetadata.numInputs;
    usedTextures[0] = xboxMetadata.usedTextures[0];
    usedTextures[1] = xboxMetadata.usedTextures[1];

    const GfxClipParameters& clip_parameters = mXboxClipParameters;'''
    return once(text,old,new)
