"""Shipyard material replay, tile retention, texel decode and framebuffer discards.

Mode decodes and texture-cache nodes are memoized across draws and replays;
exact tile repeats keep their imports while the pipeline key proves them
current; RGBA5551 importers expand texels by table. Run defers its depth-only
game clear so a certified full opaque first fill discards retained color, and
the game target's depth (never read after Run) is not stored.
"""
from xbox360_platform import fast3d_framebuffer_discard, fast3d_material_replay, texture_state
from profile_projections import once

MODE_SHA256 = "a3727640520169b529895aca9b1b7cacbf14dd6dfdd8feaac6d565120c8e0a22"

# GfxDrawRectangle's NDC edges for an inactive framebuffer after FILL's
# inclusive edge, with its widescreen policy and AdjustVIewportOrScissor viewport.
X = "(%s / (4.0f * HALF_SCREEN_WIDTH(mActiveFrameBuffer)) - 1.0f)"
Y = "(-(%s / (4.0f * HALF_SCREEN_HEIGHT(mActiveFrameBuffer))) + 1.0f)"
VIEWPORT = """        XYWidthHeight xboxViewport = { 0, (int16_t)mNativeDimensions.height, mNativeDimensions.width,
                                       mNativeDimensions.height };
        AdjustVIewportOrScissor(&xboxViewport);"""


def _x(name):
    edge = X % name
    return "(mWidescreenActive ? " + edge + " : AdjXForAspectRatio(" + edge + "))"


def header(text):
    anchor = "    unsigned mXboxPipelineCertified;\n"
    return once(text, anchor, anchor + "    bool mXboxCanDiscardGameColor = false;\n")


def transform(text):
    text = fast3d_material_replay.install(
        text,
        function="__declspec(noinline) bool Interpreter::XboxPrepareTrianglePipeline(",
        sha256=MODE_SHA256,
        values=("use_alpha", "use_fog", "use_blend_color", "use_grayscale"),
        hoist=("    triangleTrace.Mark(SMASH_TRI_COMBINER);",),
    )
    text = texture_state.retained_tile_updates(texture_state.texel_decode(text, expected=3))
    # fb 0 was just cleared; only the retained game target may skip its restore.
    text = fast3d_framebuffer_discard.game_fill(
        text,
        clear="    (mXboxPipelineKey.valid=false, mRapi->ClearFramebuffer(false, true));",
        eligible="mRendersToFb && mMsaaLevel == 1",
        left=_x("ulx"),
        right=_x("lrx"),
        top=Y % "uly",
        bottom=Y % "lry",
        viewport=VIEWPORT,
    )
    text = fast3d_framebuffer_discard.final_depth(text, anchor="        ComposeFinalFrame();", flag=False)
    return fast3d_framebuffer_discard.presentation(text, depth="mRendersToFb", color="mRendersToFb")
