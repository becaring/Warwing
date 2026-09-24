"""Smash policy adapter for Shipyard's pinned spdlog compiler projector."""
from pathlib import Path
import importlib.util,json,sys

ROOT=Path(__file__).resolve().parents[4]
BASE=Path(__file__).parent
UP=ROOT/'upstream/dependencies/spdlog/include'
sys.dont_write_bytecode=True

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

LANG=module('logging_language',ROOT/'platform/xbox360/cpp-compat/config/lowering.py')
PRISM=module('logging_braces',ROOT/'tools/prepare_prism_xdk.py')
lock=json.loads((ROOT/'platform-base.lock.json').read_text())
PLATFORM=(ROOT/lock['base']).resolve()
SHARED=module('shipyard_logging_core',PLATFORM/'python/xbox360_platform/logging_core.py')

def configure():
    SHARED.configure(upstream=UP,base=BASE,language=LANG,syntax=PRISM,
        namespace='xbox_compat',environment_header=ROOT/'platform/xbox360/environment.h',
        environment_get='XboxEnv_Get',guard_source='SMASH360_PRISM_',
        guard_target='SMASH360_SPDLOG_',overload_mode='eager')
    return SHARED

def common():
    return configure().common()

def generate(out):
    return configure().generate(out)
