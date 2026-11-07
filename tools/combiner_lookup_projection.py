"""Smash adapter for Shipyard's combiner lookup split."""
from pathlib import Path
from platform_base import resolve

resolve(Path(__file__).resolve().parents[1])
from xbox360_platform.combiner_lookup import header, transform
