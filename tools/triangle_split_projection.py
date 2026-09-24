"""BattleShip's triangle-state boundary and observer adapter."""

from pathlib import Path

from platform_base import resolve

resolve(Path(__file__).resolve().parents[1])
from xbox360_platform import fast3d_triangle_split


BOUNDARY = '    // PORT: on the RDP, depth *comparison*'


def header(text):
    return fast3d_triangle_split.header(text, 'SmashTriangleTrace', 'triangleTrace')


def transform(text):
    return fast3d_triangle_split.transform(text, BOUNDARY, 'SmashTriangleTrace', 'triangleTrace')
