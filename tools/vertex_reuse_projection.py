"""SoH exact short conversions and within-G_VTX normal reuse, adapted to Smash.

Positional lighting remains per vertex. No position, ordinary UV, fog, alpha,
clip or source-resource lifetime is shared. Batch reuse owns only source indices.
"""
import re
from profile_projections import once

COPY_MARKER='            // Reuse only directional-light RGB and generated UVs from this load.'

def transform(text):
    start=text.index('void Interpreter::GfxSpVertex(')
    end=text.index('void Interpreter::GfxSpModifyVertex(',start)
    original=text[start:end]
    vertex=original
    vertex,count=re.subn(r'v->ob\[[012]\]',lambda m:'Smash360Fast::SignedShortFloat('+m[0]+')',vertex)
    if count!=21:raise ValueError('Re-audit vertex position conversion domain')
    for old,new in [('d->u = U;', 'd->u = Smash360Fast::SignedShortFloat(U);'),
                    ('d->v = V;', 'd->v = Smash360Fast::SignedShortFloat(V);'),
                    ('dotx * mRsp->texture_scaling_factor.s','dotx * Smash360Fast::UnsignedShortFloat(mRsp->texture_scaling_factor.s)'),
                    ('doty * mRsp->texture_scaling_factor.t','doty * Smash360Fast::UnsignedShortFloat(mRsp->texture_scaling_factor.t)'),
                    ('z * winv * mRsp->fog_mul + mRsp->fog_offset',
                     'z * winv * Smash360Fast::SignedShortFloat(mRsp->fog_mul) + Smash360Fast::SignedShortFloat(mRsp->fog_offset)')]:
        vertex=once(vertex,old,new)
    vertex=once(vertex,'    for (size_t i = 0; i < n_vertices; i++, dest_index++) {','''    uint8_t xboxShadeSources[MAX_VERTICES];
    const size_t xboxFirstVertex=dest_index;
    bool xboxReuseShade=(mRsp->geometry_mode & G_LIGHTING) &&
        !(mRsp->geometry_mode & G_LIGHTING_POSITIONAL) && vertices != nullptr &&
        n_vertices>0 && n_vertices<=MAX_VERTICES && n_vertices<=256 && dest_index<=MAX_VERTICES &&
        n_vertices<=MAX_VERTICES-dest_index &&
        Shipyard::Fast3D::VertexSourceDisjoint(vertices,n_vertices*sizeof(F3DVtx),mRsp,sizeof(*mRsp));
    if(xboxReuseShade)xboxReuseShade=Shipyard::Fast3D::BatchNormalSources(vertices,n_vertices,xboxShadeSources);
    for (size_t i = 0; i < n_vertices; i++, dest_index++) {''')
    light='        if (mRsp->geometry_mode & G_LIGHTING) {\n'
    vertex=once(vertex,light,light+'''            if (xboxReuseShade && xboxShadeSources[i]!=i) {
'''+COPY_MARKER+'''
                const LoadedVertex& source=mRsp->loaded_vertices[xboxFirstVertex+xboxShadeSources[i]];
                d->color.r=source.color.r;d->color.g=source.color.g;d->color.b=source.color.b;
                if(mRsp->geometry_mode & G_TEXTURE_GEN) {U=(short)source.u;V=(short)source.v;}
            } else {
''')
    vertex=once(vertex,'''        } else {
            d->color.r = v->cn[0];''','''            } // Original unique-normal / positional-light path.
        } else {
            d->color.r = v->cn[0];''')
    return '#include "fast3d/normal_sources.h"\n#include "fast3d/vertex_transform.h"\n'+once(text,original,vertex)
