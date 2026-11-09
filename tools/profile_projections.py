"""Diagnostic-only insertions into hash-locked production source projections.

No opcode, cache, fixup, synchronization or rendering decision is changed.
Each function anchor must be unique; the owning generator retains #line maps.
"""

import re


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Profiler source anchor changed: " + old[:100])
    return text.replace(old, new, 1)


def enter(text, name, code):
    pattern = (
        r'(?m)^[ \t]*(?:extern\s+"C"\s+)?[A-Za-z_][\w:<>,*& \t]*\b'
        + re.escape(name)
        + r"\s*\([^;{}]*\)\s*(?:const\s*)?\{"
    )
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise ValueError("Profiler expected one function: " + name + " found " + str(len(matches)))
    at = matches[0].end()
    return text[:at] + "\n    " + code + "\n" + text[at:]


def scope(text, name, section):
    return enter(text, name, "Smash360PerfScope profileScope(SMASH_PERF_" + section + ");")


def detail_scope(text, name, section):
    return enter(text, name, "Smash360PerfScope detailScope(SMASH_PERF_" + section + ", smash360_perf_detail);")


def interpreter(text):
    text = '#include "runtime/perf_trace.h"\n' + text
    for name, section in (
        ("Run", "FAST3D"),
        ("StartFrame", "FRAME_SETUP"),
        ("ComposeFinalFrame", "COMPOSE"),
        ("GfxSpMatrix", "MATRIX"),
        ("GfxSpVertex", "VERTEX"),
        ("GfxSpTri1", "TRIANGLE"),
        ("Flush", "FLUSH"),
        ("ImportTexture", "TEXTURE_IMPORT"),
        ("TextureCacheLookup", "TEXTURE_CACHE"),
        ("TextureCacheDelete", "TEXTURE_INVALIDATE"),
        ("TextureCacheDeleteRange", "TEXTURE_INVALIDATE"),
        ("TextureCacheClear", "TEXTURE_INVALIDATE"),
        ("LookupOrCreateColorCombiner", "COMBINER"),
        ("LookupOrCreateShaderProgram", "SHADER_LOOKUP"),
    ):
        text = scope(text, "Interpreter::" + name, section)
    text = scope(text, "PortTextureContentHash", "TEXTURE_HASH")
    for name, section in (
        ("portNormalizeDisplayListPointer", "DL_NORMALIZE"),
        ("gfxPointerHasReadableBytes", "POINTER_CHECK"),
        ("gfx_step", "DL_STEP"),
    ):
        # Per-command and per-pointer scopes: two time-base reads each would
        # tax every command. WARWING_PROFILE_DETAIL=1 or the sampled command
        # trace (WARWING_COMMAND_TRACE=1) measures them.
        text = detail_scope(text, name, section)
    text = enter(text, "Interpreter::GfxSpVertex", "Smash360_PerfCount(SMASH_COUNT_VERTICES, (unsigned)n_vertices);")
    text = enter(text, "Interpreter::GfxSpTri1", "Smash360_PerfCount(SMASH_COUNT_TRIANGLES);")
    text = enter(text, "gfx_step", "Smash360_PerfCount(SMASH_COUNT_COMMANDS);")
    text = once(
        text,
        "    {\n        if (sDLBoundsCheck && sDLBoundsCheck((uintptr_t)cmd) == kDLBoundsWalkedPast) {",
        """\
    {
        Smash360PerfScope boundsScope(SMASH_PERF_DL_BOUNDS, smash360_perf_detail);
        if (sDLBoundsCheck && sDLBoundsCheck((uintptr_t)cmd) == \
kDLBoundsWalkedPast) {""",
    )
    text = once(
        text,
        "    if (sGbiTraceCallback) {\n        sGbiTraceCallback(",
        "    if (sGbiTraceCallback) {\n        Smash360PerfScope traceScope(SMASH_PERF_GBI_TRACE);\n        sGbiTraceCallback(",
    )
    # Dispatch and every early return stay intact; raw opcode bytes
    # identify the workload without imposing a game/microcode classification.
    text = once(
        text,
        "    if (opcode == F3DEX2_G_LOAD_UCODE) {",
        """\
    Smash360PerfScope \
opcodeScope(Smash360_OpcodeSection(static_cast<uint8_t>(opcode)), \
smash360_perf_detail);

    if (opcode == F3DEX2_G_LOAD_UCODE) {""",
    )
    owner = "Interpreter* gfx = mInstance.lock().get();"
    if text.count(owner) != 90:
        raise ValueError("Interpreter temporary-owner sites changed")
    # The original temporary shared_ptr still dies at the same full-expression.
    # Do not replace weak ownership with a raw cache while merely measuring it.
    text = text.replace(
        owner,
        "Interpreter* gfx; { Smash360PerfScope ownerScope(SMASH_PERF_INSTANCE_ACQUIRE, smash360_perf_detail); gfx = mInstance.lock().get(); }",
    )
    text = enter(text, "PortTextureContentHash", "Smash360_PerfCount(SMASH_COUNT_HASH_BYTES, n);")
    text = once(
        text,
        "if (verify && it->second.content_hash != content_hash) {",
        "if (verify && it->second.content_hash != content_hash) {\n            Smash360_PerfCount(SMASH_COUNT_TEXTURE_STALE);",
    )
    text = once(
        text,
        "            mRapi->SelectTexture(i, it->second.texture_id);",
        "            Smash360_PerfCount(SMASH_COUNT_TEXTURE_HITS);\n            mRapi->SelectTexture(i, it->second.texture_id);",
    )
    text = once(
        text,
        "    if (mTextureCache.map.size() >= TEXTURE_CACHE_MAX_SIZE) {",
        "    Smash360_PerfCount(SMASH_COUNT_TEXTURE_MISSES);\n    if (mTextureCache.map.size() >= TEXTURE_CACHE_MAX_SIZE) {",
    )
    return text


VERTEX_PHASES = (
    ("    EnsureMatrixProduct();\n    if (XboxDeferVertices(", "VERTEX_MATRIX", True),
    ("    static_assert(sizeof(F3DVtx)==16,", "VERTEX_TRANSFORM", False),
    ("    const float xboxAspectScale=", "VERTEX_SETUP", False),
    ("    for (size_t i = 0; i < n_vertices; i++, dest_index++) {\n        bool xboxStoreShade=false;", "VERTEX_SHADE", False),
    ("    if (xboxTransformBatch) {\n        if (xboxFiniteClip) Shipyard::Fast3D::ClipFiniteVertices(", "VERTEX_CLIP", False),
)
VERTEX_COUNTS = (
    ("            if (xboxReuseShade && xboxShadeSources[i]!=i) {\n", "VERTEX_REUSE"),
    ("            if(xboxCachedShade) {\n", "VERTEX_SHADE_HIT"),
    ("            if (mRsp->geometry_mode & G_TEXTURE_GEN) {\n                float dotx = 0, doty = 0;\n", "VERTEX_TEXGEN"),
)


def vertex_phases(text):
    """Split GfxSpVertex into its phases and count each shading path; apply after every vertex projection."""
    for anchor, section, first in VERTEX_PHASES:
        code = ("Smash360PerfScope vertexPhase(SMASH_PERF_" + section + ", smash360_perf_detail);" if first
                else "vertexPhase.Switch(SMASH_PERF_" + section + ");")
        text = once(text, anchor, "    " + code + "\n" + anchor)
    for anchor, counter in VERTEX_COUNTS:
        text = once(text, anchor, anchor + "                Smash360_PerfDetailCount(SMASH_COUNT_" + counter + ");\n")
    text = once(text, "                    dotx = acosf(-dotx)",
                "                    Smash360_PerfDetailCount(SMASH_COUNT_VERTEX_TEXGEN_LINEAR);\n"
                "                    dotx = acosf(-dotx)")
    text = once(text, "            int r = mRsp->current_lights[mRsp->current_num_lights - 1].l.col[0];\n",
                "            Smash360_PerfDetailCount(SMASH_COUNT_VERTEX_LIT);\n"
                "            Smash360_PerfDetailCount(SMASH_COUNT_VERTEX_LIGHTS, (unsigned)mRsp->current_num_lights);\n"
                "            int r = mRsp->current_lights[mRsp->current_num_lights - 1].l.col[0];\n")
    return once(text, "    const float xboxAspectScale=",
                "    if (!xboxTransformBatch) Smash360_PerfDetailCount(SMASH_COUNT_VERTEX_SLOW, (unsigned)n_vertices);\n"
                "    const float xboxAspectScale=")


def port(relative, text):
    functions = {
        "port/bridge/lbreloc_bridge.cpp": (
            ("portRelocFindContainingFile", "RELOC_RANGE"),
            ("portRelocFindFileIdAndBase", "RELOC_ID"),
        ),
        "port/resource/RelocPointerTable.cpp": (("portRelocTryResolvePointer", "RELOC_TOKEN"),),
        "port/bridge/lbreloc_byteswap.cpp": (
            ("portRelocFixupVertexAtRuntime", "RELOC_VERTEX"),
            ("portRelocFixupTextureAtRuntime", "RELOC_TEXTURE"),
        ),
    }
    if relative in functions:
        text = '#include "runtime/perf_trace.h"\n' + text
        for name, section in functions[relative]:
            text = detail_scope(text, name, section)
    if relative == "port/port_dl_ranges.cpp":
        text = '#include "runtime/perf_trace.h"\n' + text
        text = once(
            text,
            "    const uint64_t gen = sRangesGen.load(std::memory_order_acquire);",
            """\
    uint64_t gen;
    { Smash360PerfScope generationScope(SMASH_PERF_BOUNDS_GENERATION, \
smash360_perf_detail);
      gen = sRangesGen.load(std::memory_order_acquire); }""",
        )
        text = once(
            text,
            "((addr - c.base) < c.size)) {\n            return PORT_DL_IN_RANGE;",
            "((addr - c.base) < c.size)) {\n            Smash360_PerfDetailCount(SMASH_COUNT_BOUNDS_HIT);\n            return PORT_DL_IN_RANGE;",
        )
        text = once(
            text,
            "    std::lock_guard<std::mutex> lk(sRangesMtx);\n    bool walked_past = false;",
            """\
    Smash360_PerfDetailCount(SMASH_COUNT_BOUNDS_MISS);
    Smash360PerfScope scanScope(SMASH_PERF_BOUNDS_SCAN, \
smash360_perf_detail);
    std::lock_guard<std::mutex> lk(sRangesMtx);
    bool walked_past = false;""",
        )
        text = once(
            text,
            "    bool walked_past = false;\n    for (const auto &e : sRanges) {",
            "    bool walked_past = false;\n    for (const auto &e : sRanges) {\n        Smash360_PerfDetailCount(SMASH_COUNT_BOUNDS_VISITS);",
        )
        text = once(
            text,
            "            sHitCache = HitCache{gen, e.base, e.size};",
            "            Smash360_PerfDetailCount(SMASH_COUNT_BOUNDS_FOUND);\n            sHitCache = HitCache{gen, e.base, e.size};",
        )
        text = once(
            text,
            "    return walked_past ? PORT_DL_WALKED_PAST : PORT_DL_UNKNOWN;",
            """\
    Smash360_PerfDetailCount(walked_past ? SMASH_COUNT_BOUNDS_PAST : \
SMASH_COUNT_BOUNDS_UNKNOWN);
    return walked_past ? PORT_DL_WALKED_PAST : PORT_DL_UNKNOWN;""",
        )
    return text


def native(text):
    text = '#include "runtime/perf_trace.h"\n' + text
    # Re-enable the original donor scopes, retaining their exact placement
    # after no-op guards for Begin/FinishFramebuffer and depth locks.
    text = text.replace("SoHPerfScope", "Smash360PerfScope").replace("SOH_PERF_", "SMASH_PERF_")
    for name, section in (
        ("Compile", "SHADER_CODE"),
        ("CollectTextures", "TEXTURE_COLLECT"),
        ("ReleaseTexture", "TEXTURE_RELEASE"),
        ("RestoreQuad", "RESTORE_QUAD"),
        ("UpdateFramebuffer", "FRAMEBUFFER_UPDATE"),
        ("End", "NATIVE_END"),
        ("Finish", "NATIVE_FINISH"),
    ):
        text = scope(text, name, section)
    for name, code in (
        (
            "Draw",
            """\
Smash360_PerfCount(SMASH_COUNT_DRAW_TRIANGLES, (unsigned)triangles);
    Smash360_PerfCount(SMASH_COUNT_DRAW_BYTES, \
(unsigned)(count*sizeof(float)));""",
        ),
        ("Upload", "Smash360_PerfCount(SMASH_COUNT_UPLOAD_BYTES, width*height*4);"),
        ("SetNativeTexture", "Smash360_PerfCount(SMASH_COUNT_NATIVE_BINDS);"),
    ):
        text = enter(text, name, code)
    text = once(
        text,
        "    HRESULT hr = D3DXCompileShader(source.c_str(), (UINT)source.size(), NULL, NULL, entry, profile, 0, &code, &errors, NULL);",
        "    HRESULT hr;\n    { Smash360PerfScope compileScope(SMASH_PERF_SHADER_COMPILE);\n"
        "      hr = D3DXCompileShader(source.c_str(), (UINT)source.size(), NULL, NULL, entry, profile, 0, &code, &errors, NULL); }",
    )
    for call, section in (
        (
            """\
Smash360_Check(smash_device->DrawPrimitiveUP(D3DPT_TRIANGLELIST,\
(UINT)triangles,vertices,(UINT)(current_shader->floats*4)),\"SoH \
DrawPrimitiveUP\");""",
            "DRAW_UP",
        ),
        (
            'Smash360_Check(smash_device->EndTiling(0,NULL,NULL,&clear,1,0,NULL),"finish framebuffer tiling");',
            "END_TILING",
        ),
        (
            'Smash360_Check(smash_device->CreateTexture(width, height, 1, 0, D3DFMT_LIN_A8R8G8B8, D3DPOOL_DEFAULT, &tex.native, NULL), "CreateTexture");',
            "TEXTURE_CREATE",
        ),
        ('Smash360_Check(tex.native->LockRect(0, &lock, NULL, 0), "texture LockRect");', "TEXTURE_LOCK"),
    ):
        text = once(text, call, "{ Smash360PerfScope callScope(SMASH_PERF_" + section + "); " + call + " }")
    if text.count("smash_device->BlockUntilIdle();") != 3:
        raise ValueError("Native explicit GPU-idle sites changed")
    text = text.replace(
        "smash_device->BlockUntilIdle();",
        "{ Smash360PerfScope idleScope(SMASH_PERF_GPU_IDLE); smash_device->BlockUntilIdle(); }",
    )
    return text


def gui(text):
    text = '#include "runtime/perf_trace.h"\n' + text
    for name, section in (("StartDraw", "GUI_START"), ("EndDraw", "GUI_END"), ("ImGuiRenderDrawData", "GUI_RENDER")):
        text = scope(text, "Gui::" + name, section)
    return text
