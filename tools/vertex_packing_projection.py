"""Reuse SoH exact byte colors and local output cursor in BattleShip's packer.

Only the audited production triangle packing loop is changed. Material choices,
UV/FB transforms, byte quantization, stream order and Flush remain game-owned.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
from platform_base import resolve
BASE = resolve(ROOT)
from xbox360_platform.vertex_stream import lower

START='    for (int i = 0; i < 3; i++) {\n        float z'
END='    if (++mBufVboNumTris == MAX_TRI_BUFFER)'
COLOR=r'(mRdp->(?:blend_color|fog_color|grayscale_color)\.[rgba]|v_arr\[i\]->color\.a|color->[rgba]) / 255\.0f'

def transform(text):
    return lower(text, start=START, end=END, color_pattern=COLOR,
                 namespace='Shipyard::Fast3D', cursor='xboxVertexOutput',
                 expected_writes=25, expected_colors=17)
