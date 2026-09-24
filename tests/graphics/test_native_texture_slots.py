"""Check the physical Shipyard binding helper against SDK constant-slot advice."""
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import prepare_graphics_xdk as graphics


def binding_source():
    source = (graphics.PLATFORM_BASE / 'sources/xenos/core.cpp').read_text()
    start = source.index('HRESULT SetNativeTexture(')
    end = source.index('\n}', start) + 2
    return source[start:end]


def number(text):
    return int(text[:-1], 16) if text.endswith('h') else int(text, 0)


def path_until_sdk_call(assembly, slot):
    """Small fail-closed evaluator for this helper's integer dispatch only."""
    rows = re.findall(r'(?m)^[ \t]*([0-9A-Fa-f]{8}):[ \t]+[0-9A-Fa-f]{8}[ \t]+(\S+)[ \t]*([^;\n]*)', assembly)
    instructions = {int(address, 16): (opcode, operands.strip()) for address, opcode, operands in rows}
    regs, pc, comparison, visited = {'r4': slot}, 0, None, []
    for _ in range(128):
        if pc not in instructions:
            raise AssertionError('Unsupported PPC path address: %x' % pc)
        op, operand = instructions[pc]
        args = [v.strip() for v in operand.split(',')]
        visited.append(op)
        if op == 'bl':
            return visited, regs
        if op in ('srd', 'sld', 'srw', 'slw'):
            raise AssertionError('Valid slot %d still executes variable shift %s' % (slot, op))
        if op == 'li':
            regs[args[0]] = number(args[1])
        elif op == 'lis':
            regs[args[0]] = number(args[1]) << 16
        elif op == 'oris':
            regs[args[0]] = regs[args[1]] | (number(args[2]) << 16)
        elif op == 'addi':
            if args[0] != 'r1': regs[args[0]] = regs[args[1]] + number(args[2])
        elif op in ('rldicl', 'rldicr'):
            value, shift, mask = regs[args[1]] & 0xffffffffffffffff, number(args[2]), number(args[3])
            value = ((value << shift) | (value >> ((64-shift) % 64))) & 0xffffffffffffffff
            regs[args[0]] = value & ((1 << (64-mask))-1 if op == 'rldicl' else
                                    (0xffffffffffffffff << (63-mask)))
        elif op in ('cmpwi', 'cmplwi'):
            value = regs[args[-2]]
            if op == 'cmplwi': value &= 0xffffffff
            comparison = value - number(args[-1])
        elif op in ('beq', 'bne', 'bgt', 'blt', 'bge', 'ble'):
            if comparison is None: raise AssertionError('Branch without proven compare')
            take = {'beq': comparison == 0, 'bne': comparison != 0,
                    'bgt': comparison > 0, 'blt': comparison < 0,
                    'bge': comparison >= 0, 'ble': comparison <= 0}[op]
            if take:
                pc = int(args[-1], 16)
                continue
        elif op == 'b':
            pc = int(args[-1], 16)
            continue
        elif op not in ('mflr', 'stw', 'stwu'):
            raise AssertionError('Unsupported instruction before SDK call: ' + op)
        pc += 4
    raise AssertionError('PPC dispatch did not reach SDK call')


class NativeTextureTests(unittest.TestCase):
    def test_native_valid_slots_have_constant_masks(self):
        out = ROOT / 'scratch/evidence/soh-parity/native-texture-test'
        out.mkdir(parents=True, exist_ok=True)
        source = binding_source().replace('HRESULT SetNativeTexture(int tile,',
            'extern "C" __declspec(noinline) HRESULT SetNativeTexture(IDirect3DDevice9* xenos_device,int tile,')
        path = out / 'binding.cpp'
        path.write_text('#include <xtl.h>\n#define Smash360_PerfCount(x) ((void)0)\n' + source)
        sdk = Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
        obj = out / 'binding.obj'
        result = subprocess.run([str(sdk/'bin/win32/cl.exe'), '/nologo', '/c', '/O2', '/Ob2',
            '/MT', '/EHsc', '/D_XBOX', '/DNOMINMAX', '/I'+str(sdk/'include/xbox'),
            '/Fo'+str(obj), str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run([str(sdk/'bin/win32/dumpbin.exe'), '/disasm', str(obj)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (out/'binding.asm').write_text(result.stdout)
        assembly = result.stdout.split('\nSetNativeTexture:\n', 1)[1].split('\n  Summary', 1)[0]
        for slot in range(6):
            ops, regs = path_until_sdk_call(assembly, slot)
            self.assertEqual(regs['r4'], slot, 'SDK sampler changed')
            # SDK D3DTAG fetch mask: top bit shifted by Sampler + 32.
            self.assertEqual(regs['r6'] & 0xffffffffffffffff, 1 << (31-slot))
        print('Six real XDK binding paths use literal masks without variable shifts')

    def test_real_helper_forwards_exactly_once(self):
        out = ROOT / 'scratch/evidence/soh-parity/native-texture-test'
        out.mkdir(parents=True, exist_ok=True)
        source = r'''
#include <stdint.h>
#include <stdio.h>
typedef long HRESULT;
struct IDirect3DTexture9 {};
struct Device {
    unsigned calls, slot; IDirect3DTexture9* texture;
    HRESULT SetTexture(unsigned s, IDirect3DTexture9* p) {
        ++calls; slot=s; texture=p; return (HRESULT)0x81234567;
    }
} device;
Device* xenos_device=&device;
#define E_INVALIDARG ((HRESULT)0x80070057)
#define Smash360_PerfCount(x) ((void)0)
''' + binding_source() + r'''
int main() {
    IDirect3DTexture9 textures[3];
    for(int slot=-32768;slot<32768;++slot)for(unsigned p=0;p<4;++p) {
        IDirect3DTexture9* texture=p?&textures[p-1]:NULL;
        device.calls=0;
        HRESULT result=SetNativeTexture(slot,texture);
        if(slot>=0 && slot<6) {
            if(device.calls!=1 || device.slot!=(unsigned)slot || device.texture!=texture ||
               result!=(HRESULT)0x81234567)return 1;
        } else if(device.calls || result!=E_INVALIDARG)return 2;
    }
    puts("262144 valid-and-invalid slot/pointer/return forwarding cases");
}
'''
        path = out/'forwarding.cpp'; path.write_text(source)
        vcvars = r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars32.bat'
        script = out/'run.cmd'
        script.write_text('@echo off\ncall "'+vcvars+'" >nul\ncl /nologo /O2 /EHsc /MT /Fe:"'+str(out/'forwarding.exe')+'" /Fo:"'+str(out/'forwarding.obj')+'" "'+str(path)+'"\nif errorlevel 1 exit /b 1\n"'+str(out/'forwarding.exe')+'"\n')
        result = subprocess.run(['cmd.exe', '/d', '/c', str(script)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())


if __name__ == '__main__': unittest.main()
