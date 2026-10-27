"""Shared TRI2 rows, run NDC cull/area, prepared UV axes, deferred lit/fog.

Apply after triangle_pipeline_projection (it installs TRI2 runs). Shipyard's
fast3d_triangle_rows shares rows only inside runs, which traces, GBI traces
and the debugger disable; area accounting and TRI_TRACE marks stay per
triangle. fast3d_prepared_axes moves combiner-used UV axes and clamp bases to
reconciliation; the live framebuffer transform is still applied per triangle.
Deferred loads replay BattleShip's widescreen clip scale and near-plane clip.
"""
from profile_projections import once
from xbox360_platform import fast3d_deferred_vertices as deferred
from xbox360_platform import fast3d_prepared_axes as axes, fast3d_triangle_rows as rows

EMIT = '__declspec(noinline) void Interpreter::XboxEmitTriangle('
RECONCILE = '__declspec(noinline) bool Interpreter::XboxPrepareTrianglePipeline(SmashTriangleTrace& triangleTrace) {'
ROUNDING = '    const uint32_t projectionRounding = Shipyard::Fast3D::ProjectionRoundingMode();\n'
CULL = '        Smash360Fast::CullProjection& p1 = sXboxCullProjection[vtx1_idx];\n'
ROWS = '''    float* xboxRows[3]={mBufVbo+mBufVboLen,mBufVbo+mBufVboLen+xboxStride,
                       mBufVbo+mBufVboLen+2*xboxStride};'''

OLD_HELPER = '''static __forceinline void XboxCoordinate3(float& a,float& b,float& c,
    float v0,float v1,float v2,int shift,float start,bool half,float dimension,float scale,float offset) {
    a=Shipyard::Fast3D::Coordinate(v0,shift,start,half,dimension)*scale+offset;
    b=Shipyard::Fast3D::Coordinate(v1,shift,start,half,dimension)*scale+offset;
    c=Shipyard::Fast3D::Coordinate(v2,shift,start,half,dimension)*scale+offset;
}'''
# Outputs may alias (rows past the pack count share row 0), so all three
# coordinates are computed before any store.
HELPER = '''static __forceinline void XboxCoordinate3(float& a,float& b,float& c,
    float v0,float v1,float v2,const Shipyard::Fast3D::CoordinateAxis& axis,bool half,float scale,float offset) {
    float x0,x1,x2;
    if(axis.generic){x0=axis.Apply(v0,half);x1=axis.Apply(v1,half);x2=axis.Apply(v2,half);}
    else Shipyard::Fast3D::ApplyCoordinate3(axis,v0,v1,v2,half,x0,x1,x2);
    a=x0*scale+offset;b=x1*scale+offset;c=x2*scale+offset;
}'''

OLD_AXES = '''        const FbUvTransform& xf=mFbUvTransform[t];
        XboxCoordinate3(xboxRows[0][xboxOffset],xboxRows[1][xboxOffset],xboxRows[2][xboxOffset],
            v_arr[0]->u,v_arr[1]->u,v_arr[2]->u,mRdp->texture_tile[tile].shifts,
            mRdp->texture_tile[tile].uls,xboxHalfTexel,xboxTextureWidth[t],xf.scaleU,xf.offsetU);
        ++xboxOffset;
        XboxCoordinate3(xboxRows[0][xboxOffset],xboxRows[1][xboxOffset],xboxRows[2][xboxOffset],
            v_arr[0]->v,v_arr[1]->v,v_arr[2]->v,mRdp->texture_tile[tile].shiftt,
            mRdp->texture_tile[tile].ult,xboxHalfTexel,xboxTextureHeight[t],xf.scaleV,xf.offsetV);
        ++xboxOffset;
        if(tm & (1<<(2*t))) {
            float limit=(xboxTextureBoundWidth[t]-0.5f)/xboxTextureWidth[t];
            limit=limit*xf.scaleU+xf.offsetU;'''
NEW_AXES = '''        const FbUvTransform& xf=mFbUvTransform[t];
        // Combiner-used axes were prepared at reconciliation; the key compares
        // their tiles and extents. Shader-only slots prepare per triangle.
        const bool xboxPrepared=comb->usedTextures[t]!=0;
        Shipyard::Fast3D::CoordinateAxis xboxAxis[2];
        if(!xboxPrepared) {
            xboxAxis[0].Prepare(mRdp->texture_tile[tile].shifts,mRdp->texture_tile[tile].uls,tex_width[t]);
            xboxAxis[1].Prepare(mRdp->texture_tile[tile].shiftt,mRdp->texture_tile[tile].ult,tex_height[t]);
        }
        XboxCoordinate3(xboxRows[0][xboxOffset],xboxRows[1][xboxOffset],xboxRows[2][xboxOffset],
            v_arr[0]->u,v_arr[1]->u,v_arr[2]->u,xboxPrepared?mXboxAxisS[t]:xboxAxis[0],
            xboxHalfTexel,xf.scaleU,xf.offsetU);
        ++xboxOffset;
        XboxCoordinate3(xboxRows[0][xboxOffset],xboxRows[1][xboxOffset],xboxRows[2][xboxOffset],
            v_arr[0]->v,v_arr[1]->v,v_arr[2]->v,xboxPrepared?mXboxAxisT[t]:xboxAxis[1],
            xboxHalfTexel,xf.scaleV,xf.offsetV);
        ++xboxOffset;
        if(tm & (1<<(2*t))) {
            float limit=xboxPrepared?mXboxClampS[t]:(xboxTextureBoundWidth[t]-0.5f)/xboxTextureWidth[t];
            limit=limit*xf.scaleU+xf.offsetU;'''
OLD_CLAMP_T = '            float limit=(xboxTextureBoundHeight[t]-0.5f)/xboxTextureHeight[t];'
NEW_CLAMP_T = '            float limit=xboxPrepared?mXboxClampT[t]:(xboxTextureBoundHeight[t]-0.5f)/xboxTextureHeight[t];'

# Same scale and clip as the eager transform batch, including the near plane.
POSITIONS = '''    const float xboxAspectScale = !mFbActive ? GetWidescreenClipXScale() : 1.0f;
    if (!mFbActive)
        for (size_t i = 0; i < n_vertices; ++i)
            d[i].x = d[i].x * xboxAspectScale;
    if (mFbActive || Shipyard::Fast3D::FiniteUnitClipScale(xboxAspectScale))
        Shipyard::Fast3D::ClipFiniteVertices(d, n_vertices, true);
    else
        Shipyard::Fast3D::ClipVertices(d, n_vertices, true);
'''

AREA_ROUNDING = '        const uint32_t projectionRounding = Shipyard::Fast3D::ProjectionRoundingMode();\n'
AREA_LOAD = '            Smash360Fast::CullProjection& projection = sXboxCullProjection[projectionIndices[i]];\n'


def header(text):
    text = axes.header(text, '    XboxTrianglePipelineResult mXboxPipelineResult;')
    text = deferred.header(text, member='    XboxTrianglePipelineResult mXboxPipelineResult;')
    return rows.header(text, '    XboxTrianglePipelineResult mXboxPipelineResult;')


def _method(text, signature, edit):
    start = text.index(signature) if text.count(signature) == 1 else -1
    if start < 0:
        raise ValueError('Triangle path anchor drift: ' + signature)
    end = text.index('\n}', start) + 2
    return text[:start] + edit(text[start:end]) + text[end:]


def transform(text):
    text = '#include "fast3d/coordinate_three.h"\n' + text
    text = once(text, OLD_HELPER, HELPER)
    text = axes.capture(text, '    mXboxPipelineKey.Capture(*this,p);',
                        clamp_s='(xboxTextureBoundWidth[i]-0.5f)/xboxTextureWidth[i]',
                        clamp_t='(xboxTextureBoundHeight[i]-0.5f)/xboxTextureHeight[i]')
    text = rows.source(text, constructor='    mBufVbo = new float[MAX_TRI_BUFFER * (32 * 3)];',
                       draw='        mRapi->DrawTriangles(mBufVbo, mBufVboLen, mBufVboNumTris);',
                       entry=RECONCILE, buffer='constexpr size_t MAX_TRI_BUFFER = 256;')

    # The cull's FPSCR read moves into the cached-projection branch.
    def cull(body):
        body = once(body, ROUNDING, '')
        return once(body, CULL, '    ' + ROUNDING + CULL)
    text = _method(text, 'void Interpreter::GfxSpTri1(', cull)
    text = rows.cull(text, first='    ' + ROUNDING)

    def emit(body):
        body = once(body, OLD_AXES, NEW_AXES)
        body = once(body, OLD_CLAMP_T, NEW_CLAMP_T)
        # Area accounting reads the run's x/w, y/w that the cull just loaded.
        body = once(body, AREA_ROUNDING, '        const uint32_t projectionRounding = '
                    'mXboxTriangles.run ? 0 : Shipyard::Fast3D::ProjectionRoundingMode();\n')
        return once(body, AREA_LOAD, '''            if (mXboxTriangles.run) {
                mXboxTriangles.ndc.Load(projectionIndices[i], *v_arr[i], sx[i], sy[i]);
                continue;
            }
''' + AREA_LOAD)
    text = _method(text, EMIT, emit)
    text = rows.column_emitter(text, signature=EMIT, rows=ROWS, end='    mBufVboLen += 3*xboxStride;',
                               uses=16, loops=7)
    return deferred.source(text, constructor='    mBufVbo = new float[MAX_TRI_BUFFER * (32 * 3)];',
                           positions=POSITIONS,
                           emit='    XboxEmitTriangle(vtx1_idx, vtx2_idx, vtx3_idx, is_rect, triangleTrace);')
