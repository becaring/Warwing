"""Hash-locked syntax adaptation of pinned Prism and BattleShip DX11 builder."""
from pathlib import Path
import argparse
import difflib
import hashlib
import json
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE=resolve_platform_base(ROOT)
BASE=ROOT/'platform/xbox360/cpp-compat/prism'
OUT=ROOT/'scratch/prism-xdk'
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'scratch/host-python'))
import tree_sitter as ts
import tree_sitter_cpp
PARSER=ts.Parser(ts.Language(tree_sitter_cpp.language()))


def check_bytes(data,expected,name):
    if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('SHA-256 source drift: '+name)


def once(text,old,new):
    if text.count(old)!=1:raise ValueError('Expected exactly one anchor: '+old[:100])
    return text.replace(old,new,1)


# Shared lowering owns the compiler syntax transform. The pinned source and
# Release-only Prism debug guard remain Smash preparation policy.
from xbox360_platform.prism import (
    PrismProjector, braces as _braces, enum_wrappers, field, tx, walk,
)
PROJECTOR=PrismProjector(PARSER,'1de054450e7b3c5f777d2e3dfcb228ad120c329d')


def lower_ranges(source):
    return PROJECTOR.lower_ranges(source)


def aggregates(text):
    return PROJECTOR.aggregates(text)


def braces(text):
    return _braces(text,PARSER)


def lower(text,name):
    if name=='processor.cpp':
        text=once(text,'#include <spdlog/spdlog.h>','#if defined(SPDLOG_ACTIVE_LEVEL) && SPDLOG_ACTIVE_LEVEL <= 1\n#include <spdlog/spdlog.h>\n#endif')
        text=once(text,'    SPDLOG_DEBUG("Prism script: {} v{} by {}", name, version, author);','#if defined(SPDLOG_ACTIVE_LEVEL) && SPDLOG_ACTIVE_LEVEL <= 1\n    SPDLOG_DEBUG("Prism script: {} v{} by {}", name, version, author);\n#endif')
    return PROJECTOR.lower(text,name)

def mapped(source_path,text,output):
    original=(ROOT/source_path).read_text(encoding='utf-8-sig').splitlines(keepends=True)
    changed=text.splitlines(keepends=True);origins={}
    for block in difflib.SequenceMatcher(None,original,changed,autojunk=False).get_matching_blocks():
        for i in range(block.size):origins[block.b+i]=block.a+i+1
    destination=str(output.relative_to(ROOT)).replace('\\','/')
    result=[];guard=None
    if output.suffix=='.h':
        guard='SMASH360_PRISM_'+hashlib.sha256(destination.encode()).hexdigest().upper()
        result=['#ifndef '+guard+'\n','#define '+guard+'\n']
    comment=False;quote=None;continuation=False;last_file=None;last_line=0
    for index,current in enumerate(changed):
        filename=source_path if index in origins else destination
        number=origins.get(index,len(result)+2)
        if not comment and not quote and not continuation and (filename!=last_file or number!=last_line+1):
            result.append('#line %d "%s"\n'%(number,filename));last_file=filename;last_line=number-1
        result.append(current);last_line+=1
        cursor=0
        while cursor<len(current):
            pair=current[cursor:cursor+2];char=current[cursor]
            if comment:
                if pair=='*/':comment=False;cursor+=2;continue
            elif quote:
                if char=='\\':cursor+=2;continue
                if char==quote:quote=None
            elif pair=='//':break
            elif pair=='/*':comment=True;cursor+=2;continue
            elif char in ('"',"'"):quote=char
            cursor+=1
        continuation=current.rstrip('\r\n').endswith('\\')
    if guard:result.append('\n#endif\n')
    output.parent.mkdir(parents=True,exist_ok=True)
    content=''.join(result).encode('utf-8')
    # Shared consumers may currently have unchanged generated headers open.
    # Deterministic regeneration need not rewrite those bytes or their mtimes.
    if not output.is_file() or output.read_bytes()!=content:
        output.write_bytes(content)


def builder(source,compat):
    start=source.index('#define RAND_NOISE')
    end=source.index('// --------------------------------------------------------------------------',start)
    text=source[start:end]
    start=text.index('std::optional<std::string> dx_include_fs')
    end=text.index('std::string gfx_direct3d_common_build_shader',start)
    text=text[:start]+'''std::optional<std::string> dx_include_fs(const std::string& path) {
    std::string contents;
    if(!Smash360_LoadShaderResource(path,contents))return std::nullopt;
    return contents;
}

'''+text[end:]
    start=text.index('    auto init = std::make_shared<Ship::ResourceInitData>();')
    end=text.index('    processor.load(*shader);',start)+len('    processor.load(*shader);')
    text=text[:start]+'''    const char* shaderName = Fast::gfx_get_shader(cc_features.shader_id);
    std::string path = "shaders/directx/default.shader.hlsl";
    if(shaderName != nullptr)path=std::string(shaderName)+".hlsl";
    // Preserve pinned DX11 behavior: it computes path above but loads default.
    std::string shader;
    if(!Smash360_LoadShaderResource("shaders/directx/default.shader.hlsl",shader))
        throw prism::RuntimeError("Failed to load default directx shader, missing f3d.o2r?");
    processor.load(shader);'''+text[end:]
    if compat:
        begin=text.index('    prism::ContextItems mContext = {')
        end=text.index('\n    };',begin)+len('\n    };')
        entries=text[begin:end].splitlines()[1:-1]
        assignment=['    prism::ContextItems mContext;']
        for entry in entries:
            match=re.fullmatch(r'\s*\{ "([^"]+)", (.*) \},',entry)
            if not match:raise ValueError('Unexpected shader context entry: '+entry)
            expression=match[2]
            # Pinned SHADER constants are anonymous-enum values 0..14. Their
            # std::variant alternative is int. XDK has no underlying_type for
            # general non-narrowing enum selection; preserve this exact choice.
            if re.fullmatch(r'SHADER_[A-Z0-9_]+',expression):expression='static_cast<int>('+expression+')'
            assignment.append('    mContext["'+match[1]+'"] = prism::ContextTypes('+expression+');')
        text=text[:begin]+'\n'.join(assignment)+text[end:]
    text='#include "prism_shader_builder.h"\n#include "prism/processor.h"\n#include "shader_constants.h"\nnamespace Fast {\n'+text+'\n}\n'
    return lower(text,'shader_builder.cpp') if compat else text


def prepare():
    lock=json.loads((BASE/'source-lock.json').read_text(encoding='utf-8-sig'))
    source={}
    for name,sha in lock['source'].items():
        data=(ROOT/name).read_bytes();check_bytes(data,sha,name)
        source[name]=data.decode('utf-8-sig').replace('\r\n','\n')
    for path,text in source.items():
        if '/prism/src/prism/' not in path:continue
        relative=path.split('/src/',1)[1]
        mapped(path,lower(text,Path(path).name),OUT/relative)
    dx='upstream/BattleShip/libultraship/src/fast/backends/gfx_direct3d11.cpp'
    mapped(dx,builder(source[dx],True),OUT/'shader_builder.cpp')
    mapped(dx,builder(source[dx],False),OUT/'reference/shader_builder.cpp')
    header='upstream/BattleShip/libultraship/include/fast/interpreter.h'
    text=source[header]
    constants=text[text.index('enum {\n    SHADER_0,'):text.index('struct ColorCombinerKey')]
    shift=re.search(r'constexpr size_t SHADER_ID_SHIFT = 16;\nconstexpr int16_t ShaderIdUnmask\(uint64_t id\) \{\n    return \(id >> SHADER_ID_SHIFT\) & 0xFFFF;\n\}',text)
    if not shift:raise ValueError('Pinned shader-id extraction changed')
    # Same definition tokens as the full generated interpreter header: do not
    # introduce a separate inline-function definition across translation units.
    constants+='\nnamespace Fast {\n'+shift[0].replace('constexpr size_t','const size_t').replace('constexpr int16_t','inline int16_t')+'\n}\n'
    mapped(header,'#pragma once\n#include <stdint.h>\n'+enum_wrappers(constants),OUT/'shader_constants.h')
    interp='upstream/BattleShip/libultraship/src/fast/interpreter.cpp'
    text=source[interp]
    decoder=text[text.index('void gfx_cc_get_features(uint64_t'):text.index('extern "C" int gfx_create_framebuffer')]
    mapped(interp,'#include "shader_provider.h"\n#include "shader_constants.h"\n'+decoder,OUT/'test_shader_features.cpp')
    fixture='tests/prism/range_contract.cpp'
    mapped(fixture,lower((ROOT/fixture).read_text(),'range_contract.cpp'),OUT/'range_contract.cpp')
    report={'source_lock':lock,'outputs':{str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file() and p.suffix in ('.cpp','.h','.c')}}
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')


def compile_xdk():
    xdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    compiler=xdk/'bin/win32/cl.exe'
    includes=[PLATFORM_BASE/'sources',PLATFORM_BASE/'sources/value_types',OUT,BASE,ROOT/'scratch/graphics-xdk/include',ROOT/'platform/xbox360/graphics',xdk/'include/xbox']
    common=[str(compiler),'/nologo','/D_XBOX','/D_WIN32','/DNOMINMAX','/D_CRT_SECURE_NO_WARNINGS','/EHsc','/MT','/W3']+['/I'+str(p) for p in includes]
    sources=[OUT/'prism/lexer.cpp',OUT/'prism/ast.cpp',OUT/'prism/processor.cpp',OUT/'prism/utils/gv.cpp',OUT/'prism/utils/invoke.c',OUT/'shader_builder.cpp',PLATFORM_BASE/'sources/graphics/shader_provider.cpp',ROOT/'platform/xbox360/graphics/shader_provider.cpp',OUT/'test_shader_features.cpp',OUT/'range_contract.cpp']
    good=True
    for source in sources:
        name=('shipyard-' if source==PLATFORM_BASE/'sources/graphics/shader_provider.cpp' else '')+source.stem
        obj=OUT/(name+'-xdk.obj')
        result=subprocess.run(common+['/TC' if source.suffix=='.c' else '/TP','/c','/Fo'+str(obj),str(source)],capture_output=True,text=True)
        log=result.stdout+result.stderr;(OUT/(name+'-xdk.log')).write_text(log)
        print(source.name+': exit '+str(result.returncode))
        if result.returncode:print(log[-8500:]);good=False
    if not good:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--compile',action='store_true');args=parser.parse_args()
    prepare()
    if args.compile:compile_xdk()
