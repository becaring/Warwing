"""Diagnostic phase boundaries only; preserve real returns, state and output."""
from profile_projections import once,enter

def transform(text):
    text='#include "runtime/triangle_trace.h"\n'+text
    text=enter(text,'Interpreter::GfxSpTri1','SmashTriangleTrace triangleTrace;')
    anchors=[
        ('    bool has_vertex_z =','STATE'),
        ('    ColorCombinerKey key;','COMBINER'),
        ('    uint32_t tm = 0;','TEXTURE'),
        ('    struct ShaderProgram* prg = comb->prg[tm];','SHADER'),
        ('    // PORT: G_ZS_PRIM source overrides','DIAGNOSTIC'),
        ("    // Accumulate this triangle's screen coverage",'AREA'),
        ('    float* xboxVertexOutput =','PACK'),
        ('    if (++mBufVboNumTris == MAX_TRI_BUFFER)','FINISH')]
    for anchor,phase in anchors:
        text=once(text,anchor,'    triangleTrace.Mark(SMASH_TRI_'+phase+');\n'+anchor)
    return text
