"""Original/projected exact-method differential; no production UI substitutes."""
from pathlib import Path
import hashlib,json,re,runpy,subprocess,sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'scratch/input-editor-xdk/tests'
MODULE=runpy.run_path(str(ROOT/'tools/prepare_input_editor_xdk.py'));PARSER=MODULE['LOWER']['PARSER'];walk=MODULE['LOWER']['walk']
SOURCE=ROOT/'upstream/BattleShip/libultraship/src/ship/window/gui/InputEditorWindow.cpp'
def methods(text):
    names=('InputEditorWindow::InitElement','InputEditorWindow::UpdateBitmaskToMappingIds','InputEditorWindow::UpdateStickDirectionToMappingIds')
    found=[]
    for node in walk(PARSER.parse(text.encode()).root_node):
        if node.type=='function_definition':
            decl=node.child_by_field_name('declarator').child_by_field_name('declarator')
            if decl and decl.text.decode() in names:found.append(node.text.decode())
    assert len(found)==3;return '\n'.join(found)
def format_audit(original,generated):
    def calls(text):
        found=[]
        for node in walk(PARSER.parse(text.encode()).root_node):
            if node.type!='call_expression':continue
            fn=node.child_by_field_name('function').text.decode()
            if fn.startswith('fmt::'):raise AssertionError('New fmt call requires explicit semantic audit')
            if fn=='StringHelper::Sprintf':
                arg=node.child_by_field_name('arguments').named_children[0]
                assert arg.type=='string_literal'
                found.append(arg.text.decode())
        return found
    before=calls(original);after=calls(generated);assert before==after
    assert not any(re.search(r'%(?:[-+ #0]*\d*(?:\.\d+)?)[aAeEfFgG]',f) for f in before)
    return {'fmt_calls':0,'sprintf_calls':len(before),'float_sprintf_calls':0,'all_sprintf_format_strings_preserved':True,'formats':before}
def main():
    OUT.mkdir(parents=True,exist_ok=True);original=SOURCE.read_text(encoding='utf-8-sig')
    generated=MODULE['transform']('src/ship/window/gui/InputEditorWindow.cpp',original)
    assert generated==MODULE['transform']('src/ship/window/gui/InputEditorWindow.cpp',original)
    locks=json.loads((ROOT/'platform/xbox360/cpp-compat/input-editor/source-lock.json').read_text())
    for relative,expected in locks.items():
        assert hashlib.sha256((ROOT/'upstream/BattleShip/libultraship'/relative).read_bytes()).hexdigest()==expected
    try:MODULE['transform']('src/ship/window/gui/InputEditorWindow.cpp',original.replace('mButtonsBitmasks = {','mButtonsBitmasks_CHANGED = {'))
    except ValueError:pass
    else:raise AssertionError('Changed initializer anchor accepted')
    (OUT/'format-audit.json').write_text(json.dumps(format_audit(original,generated),indent=2)+'\n')
    assert generated.count('#if !defined(_XBOX)')==3
    assert 'case Raphnet:' in generated # Serialized identity remains.
    vs=subprocess.check_output(['C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe','-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip()
    results=[]
    for label,text in [('original',original),('projected',generated)]:
        target=OUT/label;target.mkdir(exist_ok=True);(target/'actual_methods.inc').write_text(methods(text))
        exe=target/'contract.exe';batch=target/'build.cmd'
        batch.write_text('@echo off\ncall "'+vs+'/VC/Auxiliary/Build/vcvars64.bat" >nul\ncl /nologo /EHsc /std:c++20 /MT /I"'+str(target)+'" /I"'+str(ROOT/'platform/xbox360/cpp-compat')+'" /I"'+str(ROOT/'upstream/BattleShip/libultraship/include')+'" "'+str(ROOT/'tests/input-editor-xdk/contract.cpp')+'" /Fo"'+str(target/'contract.obj')+'" /Fe"'+str(exe)+'"\nexit /b %errorlevel%\n')
        compiled=subprocess.run(['cmd','/d','/c',str(batch)],capture_output=True,text=True);(target/'compile.log').write_text(compiled.stdout+compiled.stderr)
        if compiled.returncode:raise RuntimeError(compiled.stdout+compiled.stderr)
        result=subprocess.run([str(exe)],capture_output=True,text=True);assert result.returncode==0,result.stderr;results.append(result.stdout)
    assert results[0]==results[1];print(results[0]);print('PASS original/projected exact methods and preserved integer/string widget formats; no Xbox execution')
if __name__=='__main__':main()
