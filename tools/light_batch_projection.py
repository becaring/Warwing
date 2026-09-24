"""SoH exact light-color cache, invariant input hoists, and bounded /127.

Runs after vertex_transform_projection. Only valid nonalias batches cache RSP
values; the original per-vertex loads/conversions remain for other calls.
"""
import re
from profile_projections import once


def transform(text):
    begin=text.index('void Interpreter::CalculateNormalDir(')
    end=text.index('void Interpreter::GfxSpMatrix(',begin)
    original=text[begin:end]
    normal=once(original,'    float light_dir[3] =',
                '    const bool xboxNearestNormal=Shipyard::Fast3D::NearestRounding();\n    float light_dir[3] =')
    normal,count=re.subn(r'Smash360Fast::NormalByteFloat\(light->dir\[([012])\]\) / 127\.0f',
                        r'Smash360Fast::DivideNormalByte127(Smash360Fast::NormalByteFloat(light->dir[\1]),xboxNearestNormal)',normal)
    if count!=3:raise ValueError('Normal direction /127 domain changed')
    text=once(text,original,normal)
    begin=text.index('void Interpreter::GfxSpVertex(')
    end=text.index('void Interpreter::GfxSpModifyVertex(',begin)
    original=text[begin:end]
    vertex=once(original,'    uint8_t xboxShadeSources[MAX_VERTICES];','''    static __declspec(thread) Smash360Fast::LightColorFloats xboxLightColorCache;
    const bool xboxBatchColors=xboxTransformBatch && (mRsp->geometry_mode&G_LIGHTING) &&
        mRsp->current_num_lights>=1 && mRsp->current_num_lights<=33;
    const float (*xboxLightColors)[3]=xboxBatchColors?
        xboxLightColorCache.Prepare(mRsp->current_lights,mRsp->current_num_lights):nullptr;
    const bool xboxBatchFog=xboxTransformBatch && (mRsp->geometry_mode&G_FOG);
    const bool xboxBatchTexgen=xboxTransformBatch && (mRsp->geometry_mode&G_LIGHTING) && (mRsp->geometry_mode&G_TEXTURE_GEN);
    const float xboxFogMul=xboxBatchFog?Smash360Fast::SignedShortFloat(mRsp->fog_mul):0.0f;
    const float xboxFogOffset=xboxBatchFog?Smash360Fast::SignedShortFloat(mRsp->fog_offset):0.0f;
    const float xboxTexgenS=xboxBatchTexgen?Smash360Fast::UnsignedShortFloat(mRsp->texture_scaling_factor.s):0.0f;
    const float xboxTexgenT=xboxBatchTexgen?Smash360Fast::UnsignedShortFloat(mRsp->texture_scaling_factor.t):0.0f;
    uint8_t xboxShadeSources[MAX_VERTICES];''')
    for axis in ('s','t'):
        old='Smash360Fast::UnsignedShortFloat(mRsp->texture_scaling_factor.'+axis+')'
        # Keep the preparatory expression; replace its one original use.
        position=vertex.index('    for (size_t i = 0; i < n_vertices;')
        vertex=vertex[:position]+once(vertex[position:],old,
            '(xboxTransformBatch?xboxTexgen'+axis.upper()+':'+old+')')
    for field,name in [('fog_mul','xboxFogMul'),('fog_offset','xboxFogOffset')]:
        old='Smash360Fast::SignedShortFloat(mRsp->'+field+')'
        position=vertex.index('    for (size_t i = 0; i < n_vertices;')
        vertex=vertex[:position]+once(vertex[position:],old,'(xboxTransformBatch?'+name+':'+old+')')
    for channel,name in enumerate('RGB'):
        old='Smash360Fast::LightByteFloat((uint8_t)'+name.lower()+')'
        vertex=once(vertex,old,'(xboxBatchColors?xboxLightColors[mRsp->current_num_lights-1]['+str(channel)+']:'+old+')')
        old='Smash360Fast::LightByteFloat(mRsp->current_lights[i].l.col['+str(channel)+'])'
        if vertex.count(old)!=2:raise ValueError('Light contribution color use changed')
        vertex=vertex.replace(old,'xboxColor'+name)
    vertex=once(vertex,'                if (intensity > 0.0f) {','''                if (intensity > 0.0f) {
                    const float xboxColorR=xboxBatchColors?xboxLightColors[i][0]:Smash360Fast::LightByteFloat(mRsp->current_lights[i].l.col[0]);
                    const float xboxColorG=xboxBatchColors?xboxLightColors[i][1]:Smash360Fast::LightByteFloat(mRsp->current_lights[i].l.col[1]);
                    const float xboxColorB=xboxBatchColors?xboxLightColors[i][2]:Smash360Fast::LightByteFloat(mRsp->current_lights[i].l.col[2]);''')
    for name in ('intensity','dotx','doty'):
        vertex=once(vertex,name+' /= 127.0f;',name+' = Smash360Fast::DivideNormal127('+name+',xboxNearestNormal);')
    return '#include "fast3d/light_batch.h"\n'+once(text,original,vertex)
