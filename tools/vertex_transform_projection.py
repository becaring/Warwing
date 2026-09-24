"""Bounded SoH VMX positions/clip and replacement-matrix quantization.

Runs after vertex_reuse_projection. Original scalar statements remain the
fallback, including source aliases and exceptional matrices. No attributes are
deferred or reused here except the final clip byte of a nonalias vertex batch.
"""
from profile_projections import once


def transform(text):
    start = text.index('void Interpreter::GfxSpMatrix(')
    end = text.index('void Interpreter::GfxSpPopMatrix(', start)
    original = text[start:end]
    matrix = once(original, '    float matrix[4][4];',
                  '    __declspec(align(16)) float matrix[4][4];')
    marker = '        for (int i = 0; i < 4; i++) {'
    first = matrix.index(marker)
    finish = matrix.index('    } else {', first)
    scalar = matrix[first:finish]
    matrix = once(matrix, scalar,
                  '        if (!Shipyard::Fast3D::NearestRounding() || !Shipyard::Fast3D::QuantizeMatrix(it->second.mf, matrix)) {\n' + scalar + '        }\n')
    text = once(text, original, matrix)

    start = text.index('void Interpreter::GfxSpVertex(')
    end = text.index('void Interpreter::GfxSpModifyVertex(', start)
    original = text[start:end]
    vertex = once(original, '    uint8_t xboxShadeSources[MAX_VERTICES];', '''    static_assert(sizeof(F3DVtx)==16,"SoH vertex input stride");
    static_assert(sizeof(LoadedVertex)==Shipyard::Fast3D::ClipVertexStride &&
                  offsetof(LoadedVertex,clip_rej)==Shipyard::Fast3D::ClipByteOffset &&
                  offsetof(LoadedVertex,x)==0,"SoH clip byte/layout contract");
    __declspec(align(16)) float xboxTransformed[MAX_VERTICES][4];
    const size_t xboxTransformFirst=dest_index;
    const bool xboxTransformBatch=vertices != nullptr && n_vertices>0 &&
        n_vertices<=MAX_VERTICES && dest_index<=MAX_VERTICES &&
        n_vertices<=MAX_VERTICES-dest_index &&
        Shipyard::Fast3D::VertexSourceDisjoint(vertices,n_vertices*sizeof(F3DVtx),mRsp,sizeof(*mRsp));
    const bool xboxNearestNormal=(xboxTransformBatch || (n_vertices && vertices!=nullptr &&
        (mRsp->geometry_mode&G_LIGHTING))) && Shipyard::Fast3D::NearestRounding();
    const bool xboxVectorPositions=xboxTransformBatch && xboxNearestNormal &&
        Shipyard::Fast3D::TransformPositions(vertices,n_vertices,mRsp->MP_matrix,xboxTransformed);
    // Bounded transform guarantees finite xyzw and normal-or-zero w. Aspect
    // may make x subnormal; the donor finite clip handles it at signed-zero w.
    const bool xboxFiniteClip=xboxVectorPositions &&
        (mFbActive || Shipyard::Fast3D::FiniteUnitClipScale(GetWidescreenClipXScale()));
    uint8_t xboxShadeSources[MAX_VERTICES];''')
    first = vertex.index('        float x = ')
    finish = vertex.index('        float world_pos[3]', first)
    scalar = vertex[first:finish]
    assign = scalar
    for name in 'xyzw':
        assign = once(assign, 'float ' + name + ' = ', name + ' = ')
    vertex = once(vertex, scalar, '''        float x,y,z,w;
        if (xboxVectorPositions) {
            x=xboxTransformed[i][0];y=xboxTransformed[i][1];
            z=xboxTransformed[i][2];w=xboxTransformed[i][3];
        } else {
''' + assign + '        }\n\n')
    first = vertex.index('        // trivial clip rejection')
    finish = vertex.index('        d->x = x;', first)
    scalar = vertex[first:finish]
    vertex = once(vertex, scalar, '        if (!xboxTransformBatch) {\n' + scalar + '        }\n\n')
    if not vertex.endswith('    }\n}\n\n'):
        raise ValueError('Vertex function tail changed; review batch clip placement')
    vertex = vertex[:-3] + '''    if (xboxTransformBatch) {
        if (xboxFiniteClip) Shipyard::Fast3D::ClipFiniteVertices(&mRsp->loaded_vertices[xboxTransformFirst],n_vertices,true);
        else Shipyard::Fast3D::ClipVertices(&mRsp->loaded_vertices[xboxTransformFirst],n_vertices,true);
    }
}

'''
    return '#include "fast3d/clip_quantize.h"\n#include "fast3d/vertex_transform.h"\n' + once(text, original, vertex)
