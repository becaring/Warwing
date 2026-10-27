"""Prepare the real pinned Fast3D interpreter in an owned XDK compiler mirror.

The full-TU audit is allowed to fail on unported actual dependencies. No fake
resource/logger/GUI facade or partial-success library is emitted.
"""

from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import sys
import profile_projections
import dispatch_owner_projection
import cull_projection
import vertex_packing_projection
import vertex_lighting_projection
import vertex_reuse_projection
import vertex_transform_projection
import light_batch_projection
import shade_cache_projection
import vertex_publication_projection
import triangle_pack_projection
import triangle_constants_projection
import combiner_lookup_projection
import texture_binding_projection
import triangle_pipeline_projection
import triangle_path_projection
import material_math_projection
import triangle_trace_projection
import triangle_split_projection
import overlap_projection
import fast3d_material_projection
import import_diag_projection
import shader_metadata_projection
import command_work_projection
import rcp_cost_projection
import bounds_cache_projection
import reloc_lookup_projection
import command_trace_projection
from prepare_prism_xdk import PARSER, walk, field, tx, once, mapped, lower_ranges, enum_wrappers
from xbox360_platform import fast3d_dispatch, fast3d_display_list_cull, fast3d_opcode, matrix_product, overlap_lus
from xbox360_platform.cpp_syntax import collect_member_defaults

ROOT = Path(__file__).resolve().parents[1]
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)
BASE = ROOT / "platform/xbox360/cpp-compat/fast3d"
OUT = ROOT / "scratch/fast3d-xdk"
UPSTREAM = ROOT / "upstream/BattleShip"
sys.path.insert(0, str(ROOT / "platform/xbox360/game-compat"))
from source_tree import stage_sources

INTERPRETER_INITIALIZERS = []
INTERPRETER_ARRAY_INITIALIZERS = []


def remove_class_defaults(text, class_name):
    text, fields = collect_member_defaults(text, class_name, PARSER, walk)
    initializers = []
    arrays = []
    for item in fields:
        if item.is_array and item.value != "{}":
            arrays.append((item.type, item.name, item.value))
        else:
            value = "" if item.is_array and item.value == "{}" else item.value
            initializers.append(item.name + "(" + value + ")")
    return text, initializers, arrays


def data_struct_constructors(text):
    """Preserve partial aggregate initialization for pure postprocess records.

    These records' scalar fields all carry defaults; the remaining fields are
    standard string/vector/record types. No POD arrays or methods are changed.
    """
    data = text.encode()
    edits = []
    for node in walk(PARSER.parse(data).root_node):
        if node.type != "struct_specifier":
            continue
        body = field(node, "body")
        name = field(node, "name")
        if not body or not name:
            continue
        members = [n for n in body.named_children if n.type != "comment"]
        if not members or any(n.type != "field_declaration" for n in members):
            continue
        values = []
        valid = True
        has_defaults = False
        for member in members:
            typ = field(member, "type")
            decls = member.children_by_field_name("declarator")
            if not typ or not decls or any(d.type != "field_identifier" for d in decls):
                valid = False
                break
            for decl in decls:
                following = [n for n in member.children if n.start_byte >= decl.end_byte]
                default = next(
                    (n for n in following if n.type not in ("=", ",", ";", "comment")), None
                )
                if default and default.start_byte >= next(
                    (d.start_byte for d in decls if d.start_byte > decl.start_byte), member.end_byte
                ):
                    default = None
                value = tx(default) if default else tx(typ) + "()"
                values.append((tx(typ), tx(decl), value))
                has_defaults |= default is not None
                if default:
                    edits.append((decl.end_byte, default.end_byte, b""))
        if not valid or not has_defaults:
            # Leave unsupported shapes untouched, never drop their defaults.
            edits = [e for e in edits if not (body.start_byte < e[0] < body.end_byte)]
            continue
        params = ", ".join("const " + t + "& " + n + "_ = " + v for t, n, v in values)
        initializers = ", ".join(n + "(" + n + "_)" for _, n, _ in values)
        ctor = "\n    explicit " + tx(name) + "(" + params + ") : " + initializers + " {}\n"
        edits.append((body.start_byte + 1, body.start_byte + 1, ctor.encode()))
    for a, b, value in sorted(edits, reverse=True):
        data = data[:a] + value + data[b:]
    return data.decode()


def opcode_tables(text):
    text = fast3d_opcode.lower(text, PARSER, walk, fast3d_opcode.FAST3D_TABLES, composed_dispatch=True)[0]
    return fast3d_dispatch.debugger_snapshot(text)


def lower_aggregate_expressions(text):
    data = text.encode()
    edits = []

    def aggregate(typ, value):
        # C++98 aggregate initialization is available in a declaration. The
        # lambda only provides expression syntax for the same initialized data.
        return "[&]() -> " + typ + " { " + typ + " value = " + value + "; return value; }()"

    assignment_types = {
        "sReadableRegionCache[sReadableRegionCacheCount++]": "ReadableRegionCacheEntry",
        "sDiagSegWrites[sDiagSegWritesIdx]": "DiagSegWrite",
        "sDiagDLPushes[sDiagDLPushesIdx]": "DiagDLPush",
        "mRdp->texture_to_load.raw_tex_metadata": "RawTexMetadata",
        "mRdp->loaded_texture[i].raw_tex_metadata": "RawTexMetadata",
        "key": "TextureCacheKey",
        "default_viewport": "XYWidthHeight",
        "gfx->mRenderingState.viewport": "XYWidthHeight",
        "gfx->mRenderingState.scissor": "XYWidthHeight",
        "mRenderingState.viewport": "XYWidthHeight",
        "mRenderingState.scissor": "XYWidthHeight",
        "mFrameBuffers[fb]": "FBInfo",
    }
    for node in walk(PARSER.parse(data).root_node):
        if node.type == "compound_literal_expression":
            value = field(node, "value")
            typ = tx(field(node, "type"))
            if typ == "Smash360Fast3D::string_view":
                replacement = typ + "()"
            elif typ in (
                "PortPackedDisplayListInfo",
                "FbUvTransform",
                "MaskedTextureEntry",
                "FbTextureRange",
            ):
                replacement = aggregate(typ, tx(value))
            else:
                raise ValueError("Unaudited compound aggregate: " + tx(node))
            edits.append((node.start_byte, node.end_byte, replacement.encode()))
        elif (
            node.type == "assignment_expression" and field(node, "right").type == "initializer_list"
        ):
            lhs = tx(field(node, "left"))
            value = field(node, "right")
            typ = assignment_types.get(lhs)
            if not typ:
                raise ValueError("Unaudited aggregate assignment: " + lhs)
            replacement = typ + "()" if tx(value) == "{}" else aggregate(typ, tx(value))
            edits.append((value.start_byte, value.end_byte, replacement.encode()))
        elif node.type == "call_expression":
            args = field(node, "arguments")
            values = [n for n in args.named_children if n.type == "initializer_list"]
            if not values:
                continue
            function = tx(field(node, "function"))
            types = {
                "sTrustedLowVARanges.push_back": "TrustedLowVARange",
                "mTextureCache.lru.insert": "TextureCacheMapIter",
                "disp_stack.push_back": "CodeDisp",
            }
            typ = types.get(function)
            if not typ:
                raise ValueError("Unaudited aggregate argument: " + function)
            for value in values:
                edits.append((value.start_byte, value.end_byte, aggregate(typ, tx(value)).encode()))
    for a, b, value in sorted(edits, reverse=True):
        data = data[:a] + value + data[b:]
    return data.decode()


def lower(text, name):
    global INTERPRETER_INITIALIZERS, INTERPRETER_ARRAY_INITIALIZERS
    text = text.replace("#include <variant>", "#include <xbox_compat/variant.h>")
    text = text.replace("std::variant<", "xbox_compat::variant<")
    inherited = {
        "DisplayList.h": ("DisplayList", "Gfx"),
        "Matrix.h": ("Matrix", "Mtx"),
        "Vertex.h": ("Vertex", "Vtx"),
    }
    if name in inherited:
        cls, typ = inherited[name]
        text = once(
            text,
            "using Resource::Resource;",
            "explicit "
            + cls
            + "(std::shared_ptr<Ship::ResourceInitData> initData) : Resource(initData) {}",
        )
    if name.startswith("PostProcess") and name != "PostProcessTypes.h":
        text = data_struct_constructors(text)
    if name == "PostProcessChain.h":
        text, initializers, arrays = remove_class_defaults(text, "PostProcessChain")
        if arrays:
            raise ValueError("Unexpected PostProcessChain array defaults")
        text = once(
            text,
            "    PostProcessChain() = default;",
            "    PostProcessChain() : " + ", ".join(initializers) + " {}",
        )
        text = once(text, "~PostProcessChain() = default;", "~PostProcessChain() {}")
        text = once(
            text,
            "    PostProcessChain(const PostProcessChain&) = delete;\n    PostProcessChain&"
            " operator=(const PostProcessChain&) = delete;",
            "  private:\n    PostProcessChain(const PostProcessChain&);\n    PostProcessChain&"
            " operator=(const PostProcessChain&);\n  public:",
        )
        text = once(
            text,
            "externalTextures = {}",
            "externalTextures = std::vector<PostProcessShaderExternalTexture>()",
        )
    if name == "File.h":
        text = once(
            text, "struct File {", "struct File {\n    File() : BufferOffset(0), IsLoaded(false) {}"
        )
        text = once(text, "size_t BufferOffset = 0;", "size_t BufferOffset;")
        text = once(text, "bool IsLoaded = false;", "bool IsLoaded;")
    if name == "Resource.h":
        text = once(
            text,
            'inline static const std::string gAltAssetPrefix = "alt/";',
            "static const std::string gAltAssetPrefix;",
        )
        # The corresponding Resource.cpp overlay below moves mIsDirty's
        # default into the actual constructor; no state default is discarded.
        text = once(text, "bool mIsDirty = false;", "bool mIsDirty;")
        text = once(
            text,
            "using IResource::IResource;",
            "explicit Resource(std::shared_ptr<ResourceInitData> initData) :"
            " IResource(initData) {}",
        )
    if name == "Resource.cpp":
        text = once(
            text,
            "namespace Ship {",
            'namespace Ship {\nconst std::string IResource::gAltAssetPrefix = "alt/";',
        )
        text = once(text, ": mInitData(initData)", ": mInitData(initData), mIsDirty(false)")
    if name == "GfxDebugger.h":
        text = once(
            text,
            "  public:",
            "  public:\n    GfxDebugger() : mIsDebugging(false), mIsDebuggingRequested(false),"
            " mDlist(nullptr), mBreakPoint() {}",
        )
        for old, new in [
            ("bool mIsDebugging = false;", "bool mIsDebugging;"),
            ("bool mIsDebuggingRequested = false;", "bool mIsDebuggingRequested;"),
            ("F3DGfx* mDlist = nullptr;", "F3DGfx* mDlist;"),
            (
                "std::vector<const F3DGfx*> mBreakPoint = {};",
                "std::vector<const F3DGfx*> mBreakPoint;",
            ),
        ]:
            text = once(text, old, new)
    if name == "Light.h":
        text = once(
            text,
            "using Resource::Resource;",
            "explicit Light(std::shared_ptr<Ship::ResourceInitData> initData) :"
            " Resource(initData) {}",
        )
    if name == "Texture.h":
        text, initializers, arrays = remove_class_defaults(text, "Texture")
        if arrays:
            raise ValueError("Unexpected Texture array defaults")
        text = once(
            text,
            "using Resource::Resource;",
            "explicit Texture(std::shared_ptr<Ship::ResourceInitData> initData) :"
            " Resource(initData), "
            + ", ".join(initializers)
            + " {}",
        )
    if name == "Texture.cpp":
        text = once(
            text,
            "Texture::Texture() : Resource(std::shared_ptr<Ship::ResourceInitData>()) {",
            "Texture::Texture() : Resource(std::shared_ptr<Ship::ResourceInitData>()), Flags(0),"
            " HByteScale(1.0), VPixelScale(1.0), ImageData(nullptr) {",
        )
    if name == "interpreter.cpp":
        text = matrix_product.source(text)
        text = once(
            text,
            """    const std::string name = nameCStr != nullptr ? nameCStr : "";

    const bool wantActive = enabled && !name.empty();
    const bool nameChanged = name != mPostProcessName;
    const bool enabledChanged = enabled != mPostProcessEnabled;""",
            """    const char* stableName = nameCStr != nullptr ? nameCStr : "";
    const bool nameChanged = mPostProcessName != stableName;
    const bool enabledChanged = enabled != mPostProcessEnabled;
    const bool wantActive = enabled && stableName[0] != '\\0';
    if (!nameChanged && !enabledChanged &&
        (wantActive ? (mPostProcessChain.IsActive() || mPostProcessLoadFailed)
                    : !mPostProcessChain.IsActive())) {
        return;
    }
    const std::string name(stableName);""",
        )
        text = profile_projections.interpreter(text)
        text = dispatch_owner_projection.transform(text)
        text = fast3d_display_list_cull.transform(text)
        text = cull_projection.transform(text)
        text = vertex_packing_projection.transform(text)
        text = vertex_lighting_projection.transform(text)
        text = vertex_reuse_projection.transform(text)
        text = vertex_transform_projection.transform(text)
        text = light_batch_projection.transform(text)
        text = shade_cache_projection.transform(text)
        text = vertex_publication_projection.transform(text)
        text = material_math_projection.transform(text)
        text = triangle_trace_projection.transform(text)
        text = command_work_projection.interpreter(text)
        text = command_trace_projection.transform(text)
        text = triangle_split_projection.transform(text)
        text = import_diag_projection.transform(text)
        text = shader_metadata_projection.transform(text)
        text = triangle_pack_projection.transform(text)
        text = triangle_constants_projection.transform(text)
        text = combiner_lookup_projection.transform(text)
        text = texture_binding_projection.transform(text)
        text = triangle_pipeline_projection.transform(text)
        text = triangle_path_projection.transform(text)
        text = overlap_lus.texture_cache_clear(text)
        text = overlap_projection.interpreter(text)
        text = fast3d_material_projection.transform(text)
        text = rcp_cost_projection.interpreter(text)
        text = command_work_projection.skip_stubs(text)
        text = bounds_cache_projection.interpreter(text)
        text = reloc_lookup_projection.interpreter(text)
        # The UV min/max loop exists only to prepare a diagnostic log payload.
        # The callee already returns immediately when this same flag is off.
        # Keep the real later vertex UV packing and scheduler area calculations.
        text = once(
            text,
            "if (!usedTextures[t] || tex_width[t] == 0 || tex_height[t] == 0)",
            "if (!Ssb64RenderDiagEnabled() || !usedTextures[t] || tex_width[t] == 0 ||"
            " tex_height[t] == 0)",
        )
        # XDK omits aggregate zero-initialization before RDP's nested non-POD
        # constructors. Preserve modern new RDP() semantics at this one site.
        text = once(
            text,
            '#include "fast/interpreter.h"',
            '#include "fast/interpreter.h"\n#include "fast3d/value_init.h"\n#include'
            ' "runtime/runtime.h"',
        )
        text = once(
            text,
            "    mRdp = new RDP();",
            "    mRdp = Shipyard::Fast3D::NewValueInitialized<RDP>();",
        )
        # A stored Window can be destroyed before Init installs its backend.
        # Release the real resources already acquired, without dereferencing
        # a backend that has not yet been assigned.
        text = once(text, "    mWapi->Destroy();", "    if (mWapi) mWapi->Destroy();")
        text = once(
            text,
            "        mTexUploadBuffer = (uint8_t*)malloc(max_tex_size * max_tex_size * 4);",
            "        mTexUploadBuffer = (uint8_t*)malloc(max_tex_size * max_tex_size * 4);\n       "
            " if (!mTexUploadBuffer) throw std::bad_alloc();",
        )
        text = "#include <new>\n" + text
        module_start = text.index("bool gfxPointerInLoadedModule(const void* ptr) {")
        module_end = text.index("\n// Trusted low-VA static data ranges.", module_start)
        # The two actual 32-bit callers both guard <=0x0FFFFFFF. SDK
        # dev_linker_images.htm mandates every loaded XEX above 0x82000000,
        # including low preferred-base images. Keep trusted assets independent.
        if text.count("gfxPointerInLoadedModule(") != 3:
            raise ValueError("Changed loaded-module callers")
        if (
            "if (i > 0x0FFFFFFFu)" not in text
            or "if (i <= 0x0FFFFFFF && !gfxPointerInLoadedModule" not in text
        ):
            raise ValueError("Changed low-address module query domain")
        text = (
            text[:module_start]
            + """static bool gfxLowPointerInLoadedModule(const void* ptr) {
    return Smash360Fast3D::LowAddressInLoadedModule(ptr);
}
"""
            + text[module_end:]
        )
        text = text.replace("gfxPointerInLoadedModule(", "gfxLowPointerInLoadedModule(")
        text = opcode_tables(text)
        # This pinned TU contains no GUI/ImGui/SDL expression or type use.
        # Its RunGuiOnly method composes framebuffers via rendering APIs.
        text = once(
            text,
            '#include "ship/window/gui/Gui.h"',
            "// Gui.h was an unused transitive dependency in this TU.\n#include"
            ' <spdlog/spdlog.h>\n#include "fast3d/platform.h"\n#include "cvars.h"',
        )
        text = once(
            text,
            "Interpreter::Interpreter() {",
            "Interpreter::Interpreter() : " + ", ".join(INTERPRETER_INITIALIZERS) + " {",
        )
        for typ, name_, value in INTERPRETER_ARRAY_INITIALIZERS:
            text = once(
                text,
                "    mRsp = new RSP();",
                "    const "
                + typ
                + " initial_"
                + name_
                + "[] = "
                + value
                + ";\n    memcpy("
                + name_
                + ", initial_"
                + name_
                + ", sizeof("
                + name_
                + "));\n    mRsp = new RSP();",
            )
        text = once(text, "#include <windows.h>", "#include <xtl.h>")
        text = once(text, "#include <any>", "// <any> is unused in this pinned translation unit.")
        text = once(text, "#include <atomic>", '#include "atomic/atomic.h"')
        text = once(text, "#include <mutex>", '#include "async/native.h"')
        text = text.replace("std::mutex", "xbox_compat::mutex").replace(
            "std::lock_guard", "xbox_compat::lock_guard"
        )
        text = text.replace(
            "std::atomic<int> sArmedImportCaptureN{0}",
            "Shipyard::Atomic::atomic<int,Shipyard::Atomic::native_relaxed_counter>"
            " sArmedImportCaptureN(0)",
        )
        text = text.replace("std::memory_order_relaxed", "Shipyard::Atomic::memory_order_relaxed")
        text = text.replace("thread_local ", "__declspec(thread) ")
        text = once(
            text,
            "sReadableRegionCache[kReadableRegionCacheCapacity]{};",
            "sReadableRegionCache[kReadableRegionCacheCapacity] = {};",
        )
        text = once(
            text,
            "for (const auto& [source, info] : sPortPackedDisplayListCache) {",
            "for (const auto& entry : sPortPackedDisplayListCache) {\n        const auto& source ="
            " entry.first; const auto& info = entry.second;",
        )
        text = text.replace("std::clamp(", "Smash360Fast3D::Clamp(")
        text = re.sub(r"(?<![\w:])(?:std::)?getenv\(", "XboxEnv_Get(", text)
        text = text.replace("round(width *", "Smash360Fast3D::RoundViewport(width *").replace(
            "round(height *", "Smash360Fast3D::RoundViewport(height *"
        )
        text = once(text, "lrintf(f * 65536.0f)", "Smash360Fast3D::RoundMatrixWord(f * 65536.0f)")
        if text.count("mTextureCache.map.reserve(TEXTURE_CACHE_MAX_SIZE)") != 2:
            raise ValueError("Changed texture cache reserve sites")
        text = text.replace(
            "mTextureCache.map.reserve(TEXTURE_CACHE_MAX_SIZE)",
            "Smash360Fast3D::ReserveEntries(mTextureCache.map, TEXTURE_CACHE_MAX_SIZE)",
        )
        # This exact source map holds scalar depth values only. No references,
        # iterators or node identity from res escape; it dies at this function's
        # end. Existing destination values remain unchanged, as for merge.
        text = once(
            text,
            "mGetPixelDepthCached.merge(res);",
            "mGetPixelDepthCached.insert(res.begin(), res.end());",
        )
        text = once(
            text, "masked.find(basePath)", "Smash360Fast3D::FindStringView(masked,basePath)"
        )
        text = once(text, "std::string(basePath)", "basePath.str()")
        text = once(
            text,
            "mMaskedTextures.find(GetBaseTexturePath(metadata.resource->GetInitData()->Path))",
            "Smash360Fast3D::FindStringView(mMaskedTextures,GetBaseTexturePath(metadata.resource->GetInitData()->Path))",
        )
        if text.count("mMaskedTextures.find(texPath)") != 2:
            raise ValueError("Changed texture-view lookup sites")
        text = text.replace(
            "mMaskedTextures.find(texPath)",
            "Smash360Fast3D::FindStringView(mMaskedTextures,texPath)",
        )
        text = text.replace(
            "mFailedShaderKeys.contains(key)",
            "(mFailedShaderKeys.find(key) != mFailedShaderKeys.end())",
        )
        text = text.replace("std::string_view", "Smash360Fast3D::string_view")
        text = lower_aggregate_expressions(text)
        for index, typ in enumerate(
            [
                "std::array<const uint32_t (*)[7], 6>",
                "std::array<const char*, 16>",
                "std::array<const char*, 8>",
            ]
        ):
            match = re.search(r"constexpr std::array (\w+) = \{(.*?)\n\s*\};", text, re.S)
            if not match:
                raise ValueError("Missing CTAD array " + str(index))
            text = (
                text[: match.start()]
                + "const "
                + typ
                + " "
                + match[1]
                + " = {{"
                + match[2]
                + "\n}};"
                + text[match.end() :]
            )
        text = once(text, "#include <algorithm>", "#include <algorithm>\n#include <array>")
        text = once(text, "bool usedTextures[2]{};", "bool usedTextures[2] = {};")
        text = re.sub(
            r"RawTexMetadata (\w+) = \{\};", r"RawTexMetadata \1 = RawTexMetadata();", text
        )
        text = once(
            text, "PostProcessParams params{};", "PostProcessParams params = PostProcessParams();"
        )
        text = text.replace(
            "mGetPixelDepthPending.emplace(x, y)",
            "mGetPixelDepthPending.insert(std::make_pair(x, y))",
        )
        # The value object above is constructed before either call, so using a
        # pair with insert preserves emplace's construction and ownership here.
        call = re.search(r"^    sPortPackedDisplayListCache\.emplace\(dlist,.*\);$", text, re.M)
        if not call:
            raise ValueError("Packed DL cache emplace changed")
        replacement = (
            call[0].replace(".emplace(dlist,", ".insert(std::make_pair(dlist,")[:-2] + "));"
        )
        text = text[: call.start()] + replacement + text[call.end() :]
        from platform_base import resolve as resolve_platform_base

        resolve_platform_base(ROOT)
        from xbox360_platform.cpp_syntax import lower_if_initializers

        text = lower_if_initializers(text, PARSER, walk)
        text = lower_ranges(text.encode()).decode()
        text = '#include "prism/compat.h"\n' + text
    if name == "interpreter.h":
        text = matrix_product.header(text)
        text = shader_metadata_projection.header(text)
        text = shade_cache_projection.header(text)
        text = triangle_constants_projection.header(text)
        text = combiner_lookup_projection.header(text)
        text = texture_binding_projection.header(text)
        text = triangle_pipeline_projection.header(text)
        text = triangle_path_projection.header(text)
        text = triangle_split_projection.header(text)
        text = command_work_projection.header(text)
        text = fast3d_material_projection.header(text)
        text, INTERPRETER_INITIALIZERS, INTERPRETER_ARRAY_INITIALIZERS = remove_class_defaults(
            text, "Interpreter"
        )
        text, initializers, arrays = remove_class_defaults(text, "GfxExecStack")
        if arrays:
            raise ValueError("Unexpected GfxExecStack array defaults")
        # The three removed empty member initializers are containers; their
        # implicit default construction already has the exact same behavior.
        if len(initializers) != 3:
            raise ValueError("Changed GfxExecStack defaults")
        for struct_name in ("ShaderPermutation", "ShaderPrewarmProgress"):
            start = text.index("struct " + struct_name + " {")
            end = text.index("\n};", start) + 3
            text = text[:start] + data_struct_constructors(text[start:end]) + text[end:]
        text = once(
            text,
            "float h_byte_scale = 1, v_pixel_scale = 1;",
            "float h_byte_scale, v_pixel_scale;\n    RawTexMetadata() : width(0), height(0),"
            " h_byte_scale(1), v_pixel_scale(1), type(TextureType::Error) {}",
        )
        text = once(text, "bool color_write_enabled = true;", "bool color_write_enabled;")
        text = once(
            text,
            "struct RenderingState {",
            "struct RenderingState {\n    RenderingState() : depth_test_and_mask(0),"
            " decal_mode(false), alpha_blend(false), color_write_enabled(true), viewport(),"
            " scissor(), mShaderProgram(nullptr), mTextures() {}",
        )
        text = once(text, "#include <span>", '#include "fast3d/views.h"')
        text = once(
            text, "#include <string_view>", "// Non-owning view operations are in fast3d/views.h."
        )
        text = once(
            text,
            "#include <compare>",
            "// Explicit key equality/order below preserve every original field.",
        )
        text = once(
            text,
            "    auto operator<=>(const ColorCombinerKey&) const = default;",
            """    bool operator==(const ColorCombinerKey& rhs) const {
        return combine_mode==rhs.combine_mode && options==rhs.options && shader_id==rhs.shader_id;
    }
    bool operator<(const ColorCombinerKey& rhs) const {
        if(combine_mode!=rhs.combine_mode)return combine_mode<rhs.combine_mode;
        if(options!=rhs.options)return options<rhs.options;
        return shader_id<rhs.shader_id;
    }""",
        )
        text = once(
            text,
            "    bool operator==(const TextureCacheKey&) const noexcept = default;",
            """    bool operator==(const TextureCacheKey& rhs) const throw() {
        return texture_addr==rhs.texture_addr && palette_addrs[0]==rhs.palette_addrs[0] &&
            palette_addrs[1]==rhs.palette_addrs[1] && fmt==rhs.fmt && siz==rhs.siz &&
            palette_index==rhs.palette_index && size_bytes==rhs.size_bytes &&
            masks==rhs.masks && maskt==rhs.maskt && tile_width==rhs.tile_width && tile_height==rhs.tile_height;
    }""",
        )
        text = once(text, "constexpr int16_t ShaderIdUnmask", "inline int16_t ShaderIdUnmask")
    text = text.replace("std::string_view", "Smash360Fast3D::string_view").replace(
        "std::span<", "Smash360Fast3D::span<"
    )
    text = text.replace("std::less<>", "std::less<std::string>")
    text = text.replace(" final :", " :").replace(" override", "")
    text = enum_wrappers(text)

    # Original default-initialized enum fields are indeterminate. Preserve that
    # behavior for omitted constructor members instead of inventing a value.
    def enum_constructors(match):
        # ShaderOpts is also defined by the generated Prism builder header;
        # retain the exact same definition tokens across those translation units.
        if match[2] == "ShaderOpts":
            return match[0]
        return (
            match[1]
            + " "
            + match[2]
            + "() {} explicit "
            + match[2]
            + "(int v) : value(static_cast<Value>(v)) {} "
        )

    text = re.sub(r"(struct (\w+) \{ enum Value \{[^}]*\}; Value value;) ", enum_constructors, text)
    # Function-pointer aliases are declarations, with no implementation change.
    text = re.sub(r"using (\w+) = ([^;]+?)\(\*\)(\([^;]*\));", r"typedef \2 (*\1)\3;", text)
    text = re.sub(r"\[\[(?:fallthrough|maybe_unused)\]\]", "", text)
    text = text.replace(" noexcept", " throw()")
    # Constants remain const; constexpr functions/classes needing runtime table
    # construction remain explicit compile work, never replaced by empty data.
    text = re.sub(r"\bconstexpr\b", "const", text)
    return text


def prepare(overlays):
    lock = json.loads((BASE / "source-lock.json").read_text())
    generated = {}
    cmake = (ROOT / "upstream/BattleShip/libultraship/cmake/cvars.cmake").read_bytes()
    if (
        hashlib.sha256(cmake).hexdigest()
        != lock["upstream/BattleShip/libultraship/cmake/cvars.cmake"]
    ):
        raise ValueError("CVar compile definition source drift")
    cvars = re.findall(r'set\((CVAR_\w+) "([^"\n]*)" CACHE STRING ""\)', cmake.decode())
    if len(cvars) != 24:
        raise ValueError("Changed CVar compile definitions")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cvars.h").write_text(
        "// Exact pinned cmake/cvars.cmake defaults.\n"
        + "".join("#define " + key + ' "' + value + '"\n' for key, value in cvars)
    )
    ordered = sorted(
        lock.items(),
        key=lambda entry: (not entry[0].endswith("/include/fast/interpreter.h"), entry[0]),
    )
    for relative, digest in ordered:
        data = (ROOT / relative).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Source drift: " + relative)
        if "/include/ship/resource/" in relative or relative.endswith(
            "/src/ship/resource/Resource.cpp"
        ):
            # Canonical actual-resource adapters now belong to the resource
            # generator. Remove only our prior owned generated duplicates.
            stale = OUT / "overlay" / relative.removeprefix("upstream/BattleShip/")
            if not stale.resolve().is_relative_to((OUT / "overlay").resolve()):
                raise ValueError("Escaped owned overlay")
            if stale.is_file():
                stale.unlink()
            continue
        if "/include/fast/" in relative or relative.endswith(
            ("/src/fast/interpreter.cpp", "/src/fast/resource/type/Texture.cpp")
        ):
            target = OUT / "overlay" / relative.removeprefix("upstream/BattleShip/")
            generated[relative] = lower(
                data.decode("utf-8-sig").replace("\r\n", "\n"), Path(relative).name
            )
            mapped(relative, generated[relative], target)
    # Preserve already validated common headers in the physical compiler tree,
    # including quoted sibling includes. No central source is overwritten.
    common = OUT / "common-overlay"
    records = []
    for source, prefix in [
        (ROOT / "scratch/graphics-xdk/include", "libultraship/include"),
        (ROOT / "scratch/audio-xdk/generated/include", "libultraship/include"),
        (ROOT / "scratch/binary-reader-xdk/generated/include", "libultraship/include"),
        (ROOT / "scratch/resources-xdk/generated/include", "libultraship/include"),
        (ROOT / "scratch/config-xdk/generated/include", "libultraship/include"),
    ]:
        for path in source.rglob("*.h"):
            target = common / prefix / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
            records.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    # Graphics PostProcessTypes supersedes its unchanged duplicate in this
    # Fast3D-owned header overlay; stage_sources intentionally rejects conflicts.
    for path in common.rglob("*.h"):
        duplicate = OUT / "overlay" / path.relative_to(common)
        if duplicate.is_file():
            duplicate.write_bytes(path.read_bytes())
    staged = stage_sources(
        UPSTREAM,
        OUT / "compile-tree",
        [
            "libultraship/src/fast/interpreter.cpp",
            "libultraship/src/fast/resource/type/Texture.cpp",
        ],
        [OUT / "overlay", common, *overlays],
    )
    (OUT / "staged-inputs.json").write_text(
        json.dumps({"common": records, "staged": staged}, indent=2)
    )
    relative = "upstream/BattleShip/libultraship/src/fast/interpreter.cpp"
    text = (ROOT / relative).read_text(encoding="utf-8-sig")
    start = text.index("void Interpreter::NormalizeVector(")
    end = text.index("void Interpreter::CalculateNormalDir(", start)
    prefix = (
        '#include "fast/interpreter.h"\n#include <array>\n#include <math.h>\n#include'
        " <string.h>\nnamespace Fast {\n"
    )
    math = text[start:end]
    cc_begin = text.index("const char* Interpreter::CCMUXtoStr(")
    cc_end = text.index("ColorCombiner* Interpreter::LookupOrCreateColorCombiner(", cc_begin)
    mapped(
        relative, prefix + math + text[cc_begin:cc_end] + "\n}\n", OUT / "test_math_original.cpp"
    )
    lowered = generated[relative]
    cc_begin = lowered.index("const char* Interpreter::CCMUXtoStr(")
    cc_end = lowered.index("ColorCombiner* Interpreter::LookupOrCreateColorCombiner(", cc_begin)
    qualifier = "__forceinline "
    if lowered[:cc_end].endswith(qualifier):
        cc_end -= len(qualifier)
    mapped(relative, prefix + math + lowered[cc_begin:cc_end] + "\n}\n", OUT / "test_math.cpp")
    start = lowered.index("struct UcodeEntry {")
    end = lowered.index("const char* GfxGetOpcodeName(", start)
    tables = lowered[start:end]
    entries = re.findall(r'\{\s*\w+\s*,\s*"[^"\n]*"\s*,\s*(\w+)\s*\}', tables)
    declarations = []
    for name in sorted(set(entries)):
        signatures = re.findall(
            r"\bbool\s+" + re.escape(name) + r"\s*\(\s*F3DGfx\s*\*\*\s*\w+\s*\)", text
        )
        if len(signatures) != 1:
            raise ValueError("Expected actual opcode handler definition: " + name)
        declarations.append(signatures[0] + ";")
    # Compile-only closure: every handler remains an unresolved REAL symbol.
    # No dummy implementations or alternate walker are generated.
    fixture = (
        '#include "fast/interpreter.h"\n#include <array>\n#include <algorithm>\nnamespace Fast'
        " {\ntypedef bool (*GfxOpcodeHandlerFunc)(F3DGfx** gfx);\n"
        + "\n".join(declarations)
        + "\n"
        + tables
        + "\n}\n"
    )
    mapped(relative, fixture, OUT / "test_opcode_tables.cpp")


def compile_xdk():
    xdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    tree = OUT / "compile-tree"
    include = [
        OUT,
        tree / "libultraship/include",
        tree / "libultraship/src",
        tree / "include",
        ROOT / "platform/xbox360",
        ROOT / "platform/xbox360/cpp-compat",
        PLATFORM_BASE / "sources/value_types",
        ROOT / "scratch/thread-pool-xdk",
        ROOT / "platform/xbox360/cpp-compat/thread-pool",
        ROOT / "platform/xbox360/cpp-compat/async",
        PLATFORM_BASE,
        PLATFORM_BASE / "sources",
        PLATFORM_BASE / "sources/json/include",
        ROOT / "scratch/json-xdk/backend-generated",
        ROOT / "scratch/logging-xdk/core-include",
        ROOT / "scratch/logging-xdk/include",
        ROOT / "upstream/dependencies/fmt-xdk",
        ROOT / "scratch/imgui-xdk/source",
        ROOT / "platform/xbox360/imgui",
        xdk / "include/xbox",
    ]
    records = []
    for relative in [
        "libultraship/src/fast/interpreter.cpp",
        "libultraship/src/fast/resource/type/Texture.cpp",
    ]:
        source = tree / relative
        name = source.stem
        command = [
            str(xdk / "bin/win32/cl.exe"),
            "/nologo",
            "/TP",
            "/EHsc",
            "/MT",
            "/W3",
            "/D_XBOX",
            "/D_WIN32",
            "/DNDEBUG",
            "/DDISABLE_SCRIPTING",
            "/D_CRT_SECURE_NO_WARNINGS",
            "/D_USE_MATH_DEFINES",
            "/I" + str(BASE),
        ]
        command += ["/I" + str(p) for p in include] + [
            "/c",
            "/Fo" + str(OUT / (name + "-xdk.obj")),
            str(source),
        ]
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        log = run.stdout + run.stderr
        (OUT / (name + "-xdk.log")).write_text(log)
        errors = [line for line in log.splitlines() if "error " in line]
        records.append(
            {"source": relative, "command": command, "exit": run.returncode, "errors": errors}
        )
        print("Full pinned Fast3D " + name + " XDK exit:", run.returncode)
        if errors:
            print("\n".join(errors[:25]))
    report = {
        "complete": all(record["exit"] == 0 for record in records),
        "translation_units": records,
        "scope": "actual full source objects; no application link or target runtime validation",
    }
    (OUT / "compile-audit.json").write_text(json.dumps(report, indent=2))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile", action="store_true")
    parser.add_argument("--source-overlay", type=Path, action="append", default=[])
    args = parser.parse_args()
    prepare(args.source_overlay)
    if args.compile:
        raise SystemExit(compile_xdk())
