"""Current post-process algorithms with upstream transpiler-OFF configuration."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
from prepare_prism_xdk import mapped,once,enum_wrappers,lower_ranges,PARSER,walk,field,tx
from prepare_fast3d_xdk import data_struct_constructors
from xbox360_platform.cpp_syntax import lower_if_initializers
ROOT=Path(__file__).resolve().parents[1]
UP=ROOT/'upstream/BattleShip/libultraship'
BASE=ROOT/'platform/xbox360/cpp-compat/postprocess'
OUT=ROOT/'scratch/postprocess-xdk'

def lower(text,name):
    text=text.replace('#include <filesystem>','#include "filesystem/filesystem.h"')
    text=text.replace('#include <mutex>','#include "async/native.h"')
    text=text.replace('std::filesystem::','xbox_compat::filesystem::').replace('std::mutex','xbox_compat::mutex').replace('std::lock_guard','xbox_compat::lock_guard')
    text=re.sub(r'\bconstexpr\b','const',text)
    text=re.sub(r'\b(PostProcess\w+)\{\}',r'\1()',text)
    text=data_struct_constructors(text)
    text=enum_wrappers(text)
    text=text.replace('std::strtof(', 'Smash360PostProcess::ParseParameterFloat(')
    if name=='PostProcessChain.cpp':
        text=once(text,'switch (t)', 'switch (t.value)')
        text=once(text,'std::lround(pixels)','Smash360PostProcess::RoundPixels(pixels)')
        text=once(text,'LoadPasses(rapi, { src }, { cfg }, {})','LoadPasses(rapi, std::vector<PostProcessSource>(1, src), std::vector<PostProcessPresetPass>(1, cfg), std::vector<PostProcessShaderExternalTexture>())')
        text=once(text,'stagedAliases.push_back({ a, i });','Alias alias = { a, i }; stagedAliases.push_back(alias);')
    if name=='PostProcessGlslNormalizer.cpp':text=once(text,'NormalizeUserGlsl(src, {})','NormalizeUserGlsl(src, std::vector<std::string>())')
    if name=='PostProcessPreset.cpp':
        text=once(text,'passes.emplace_back()','passes.push_back(PostProcessPresetPass())')
        text=once(text,'tex.emplace_back()','tex.push_back(PostProcessPresetTexture())')
        text=once(text,'PostProcessScaleType st;','PostProcessScaleType st = PostProcessScaleType::Source; // Used only after ParseScaleType succeeds.')
    if name=='PostProcessSourceLoader.cpp':
        if text.count('out.configs.emplace_back()')!=2:raise ValueError('Changed defaultpass construction')
        text=text.replace('out.configs.emplace_back()','out.configs.push_back(PostProcessPresetPass())')
        text=once(text,'MakeSource(name, std::move(raw), {})','MakeSource(name, std::move(raw), std::vector<std::string>())')
        text=once(text,'return { "scanlines", "crt-lottes" };','const std::string names[] = { "scanlines", "crt-lottes" };\n    return std::vector<std::string>(names, names+2);')
    data=text.encode();edits=[]
    for node in walk(PARSER.parse(data).root_node):
        if node.type=='call_expression' and tx(field(node,'function'))=='std::to_string':
            arg=field(node,'arguments').named_children[0]
            edits.append((arg.start_byte,arg.end_byte,('static_cast<long long>('+tx(arg)+')').encode()))
    for a,b,value in reversed(edits):data=data[:a]+value+data[b:]
    text=data.decode()
    if name=='GfxDebugger.cpp':text=once(text,'mBreakPoint = { cmds };','mBreakPoint.assign(1, cmds);')
    text=lower_if_initializers(text,PARSER,walk)
    text=lower_ranges(text.encode()).decode()
    return '#include "postprocess/compat.h"\n'+text

def prepare():
    locks=json.loads((BASE/'source-lock.json').read_text())
    for relative,digest in locks.items():
        data=(UP/relative).read_bytes()
        if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Source drift '+relative)
        text=lower(data.decode('utf-8-sig').replace('\r\n','\n'),Path(relative).name)
        mapped('upstream/BattleShip/libultraship/'+relative,text,OUT/'generated'/relative)
    (OUT/'manifest.json').write_text(json.dumps({'input_hashes':locks,'transpiler':'upstream LUS_POSTPROCESS_TRANSPILER OFF; original failure returns retained'},indent=2))

def compile_xdk():
    flags=json.loads((ROOT/'scratch/fast3d-xdk/compile-audit.json').read_text())['translation_units'][0]['command'];flags=flags[:flags.index('/c')]
    flags[1:1]=['/I'+str(ROOT/'upstream/dependencies/stb')]
    records=[]
    for source in sorted((OUT/'generated/src').rglob('*.cpp')):
        command=flags+['/c','/Fo'+str(OUT/(source.stem+'-xdk.obj')),str(source)]
        run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        log=run.stdout+run.stderr;(OUT/(source.stem+'-xdk.log')).write_text(log)
        errors=[line for line in log.splitlines() if 'error ' in line]
        print(source.stem,run.returncode);print('\n'.join(errors[:12]))
        records.append({'source':str(source.relative_to(ROOT)),'command':command,'exit':run.returncode,'errors':errors})
    (OUT/'compile-audit.json').write_text(json.dumps(records,indent=2))
    return int(any(r['exit'] for r in records))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--compile',action='store_true');args=p.parse_args()
    prepare()
    if args.compile:raise SystemExit(compile_xdk())
