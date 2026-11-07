"""Use SoH's exact byte-to-float loads and bounded FPR light accumulation.

Byte domains and bounded integral accumulators are exactly representable in
binary32. Every light still truncates its contribution; unbounded/exceptional
positive intensities permanently revert to the original 32-bit integer path.
No light state, positional-light math, generated UVs, fog or clipping changes.
"""

import re
from profile_projections import once


def transform(text):
    normal_start = "void Interpreter::CalculateNormalDir("
    normal_end = "void Interpreter::GfxSpMatrix("
    vertex_start = "void Interpreter::GfxSpVertex("
    vertex_end = "void Interpreter::GfxSpModifyVertex("
    for marker in (normal_start, normal_end, vertex_start, vertex_end):
        if text.count(marker) != 1:
            raise ValueError("Expected one authoritative vertex-light boundary: " + marker)
    start = text.index(normal_start)
    end = text.index(normal_end, start)
    original = text[start:end]
    replacement, count = re.subn(
        r"light->dir\[[012]\]", lambda m: "Smash360Fast::NormalByteFloat(" + m[0] + ")", original
    )
    if count != 3:
        raise ValueError("Light direction byte conversion contract changed: %d" % count)
    text = once(text, original, replacement)

    start = text.index(vertex_start)
    end = text.index(vertex_end, start)
    original = text[start:end]
    replacement, normals = re.subn(r"vn->n\[[012]\]", lambda m: "Smash360Fast::NormalByteFloat(" + m[0] + ")", original)
    # The original integer variables still decide the result on the fallback path.
    replacement, colors = re.subn(
        r"intensity \* (mRsp->current_lights\[i\]\.l\.col\[[012]\])",
        r"intensity * Smash360Fast::LightByteFloat(\1)",
        replacement,
    )
    if normals != 12 or colors != 3:
        raise ValueError("Vertex byte conversion contract changed: normals=%d colors=%d" % (normals, colors))

    ambient = """            int r = mRsp->current_lights[mRsp->current_num_lights - 1].l.col[0];
            int g = mRsp->current_lights[mRsp->current_num_lights - 1].l.col[1];
            int b = mRsp->current_lights[mRsp->current_num_lights - 1].l.col[2];"""
    replacement = once(
        replacement,
        ambient,
        ambient
        + """
            // 255 + 32 * 1024 * 255 < 2^23: all truncated RGB values are exact
            // binary32 integers. A later out-of-bound light permanently takes
            // the original int compound-assignment path for this vertex.
            bool xboxFloatLight = mRsp->current_num_lights >= 1 && mRsp->current_num_lights <= 33;
            float xboxLightR = Smash360Fast::LightByteFloat((uint8_t)r);
            float xboxLightG = Smash360Fast::LightByteFloat((uint8_t)g);
            float xboxLightB = Smash360Fast::LightByteFloat((uint8_t)b);""",
    )
    original_update = """                    r += intensity * Smash360Fast::LightByteFloat(mRsp->current_lights[i].l.col[0]);
                    g += intensity * Smash360Fast::LightByteFloat(mRsp->current_lights[i].l.col[1]);
                    b += intensity * Smash360Fast::LightByteFloat(mRsp->current_lights[i].l.col[2]);"""
    replacement = once(
        replacement,
        original_update,
        """\
                    if (xboxFloatLight && intensity < 1024.0f) {
                        xboxLightR = \
Smash360Fast::TruncateLightChannel(xboxLightR + intensity * \
Smash360Fast::LightByteFloat(mRsp->current_lights[i].l.col[0]));
                        xboxLightG = \
Smash360Fast::TruncateLightChannel(xboxLightG + intensity * \
Smash360Fast::LightByteFloat(mRsp->current_lights[i].l.col[1]));
                        xboxLightB = \
Smash360Fast::TruncateLightChannel(xboxLightB + intensity * \
Smash360Fast::LightByteFloat(mRsp->current_lights[i].l.col[2]));
                    } else {
                        if (xboxFloatLight) {
                            r = (int)xboxLightR;
                            g = (int)xboxLightG;
                            b = (int)xboxLightB;
                            xboxFloatLight = false;
                        }
"""
        + original_update
        + """
                    }""",
    )
    publication = "            d->color.r = r > 255 ? 255 : r;"
    replacement = once(
        replacement,
        publication,
        """            if (xboxFloatLight) {
                r = (int)xboxLightR;
                g = (int)xboxLightG;
                b = (int)xboxLightB;
            }

"""
        + publication,
    )
    return '#include "fast3d/vertex_lighting.h"\n' + once(text, original, replacement)
