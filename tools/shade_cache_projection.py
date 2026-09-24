"""Bind BattleShip's light layout to Shipyard's directional shade cache."""

from pathlib import Path

from platform_base import resolve

resolve(Path(__file__).resolve().parents[1])
from xbox360_platform.shade_cache import header, transform as project


COLOR_ACCESSOR = '''struct XboxShadeColorAt {
    template<class Light> uint8_t operator()(const Light& light, unsigned channel) const {
        return light.l.col[channel];
    }
};'''


def transform(text):
    return project(text, COLOR_ACCESSOR, 'XboxShadeColorAt')
