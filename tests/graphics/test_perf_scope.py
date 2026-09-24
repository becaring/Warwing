"""Exercise production scope accounting with an injected clock, not elapsed host time."""
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PerfScopeTests(unittest.TestCase):
    def test_nested_scope_accounting(self):
        self.compile_contract('perf_scope_contract')

    def test_command_sampling(self):
        self.compile_contract('command_trace_contract')

    def compile_contract(self, contract):
        out = ROOT / 'scratch/perf-contract'
        out.mkdir(exist_ok=True)
        vswhere = Path(os.environ['ProgramFiles(x86)']) / 'Microsoft Visual Studio/Installer/vswhere.exe'
        vs = subprocess.check_output([str(vswhere), '-latest', '-products', '*', '-requires',
                                      'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property',
                                      'installationPath'], text=True).strip()
        batch = out / 'compile.cmd'
        batch.write_text('@echo off\ncall "' + vs + '/VC/Auxiliary/Build/vcvars64.bat" >nul\n'
                         'if errorlevel 1 exit /b 1\ncl /nologo /EHsc /W4 /WX /MT /I"' +
                         str(ROOT/'platform/xbox360') + '" "' +
                         str(ROOT/('tests/graphics/'+contract+'.cpp')) + '" /Fo"' +
                         str(out/'contract.obj') + '" /Fe"' + str(out/'contract.exe') +
                         '"\nexit /b %errorlevel%\n')
        compiled = subprocess.run([os.environ['ComSpec'], '/d', '/c', str(batch)], capture_output=True, text=True)
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        result = subprocess.run([str(out/'contract.exe')], capture_output=True, text=True)
        (out/(contract+'-result.log')).write_text(result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
