"""Read-only, bounded D3D device observation in this task's recorded Xenia run.

ReadProcessMemory pattern follows Re60 causal-root-cause diagnostics. No process
memory, instruction, register or game state is written. Guest mapping candidates
follow the exact 63ea6e272 memory.cc MapViews search and are verified against EXE
instruction bytes before any device state is read.
"""
from pathlib import Path
import ctypes as c
from ctypes import wintypes as w
import hashlib, json, re, struct, sys

ROOT = Path(__file__).resolve().parents[1]
run = Path(sys.argv[1]).resolve()
if not run.is_relative_to(ROOT / 'scratch/xenia-runs'):
    raise ValueError('Run must belong to Smash360')
launch = json.loads((run / 'launch.json').read_text())
xex = Path(launch['xex'])
if hashlib.sha256(xex.read_bytes()).hexdigest().upper() != launch['xex_sha256']:
    raise ValueError('Build changed since launch')
map_text = xex.with_suffix('.map').read_text()
def address(symbol):
    hits = re.findall(r'^\s*\w+:\w+\s+' + re.escape(symbol) + r'\s+([\da-fA-F]+)\s', map_text, re.M)
    if len(hits) != 1: raise ValueError('Ambiguous symbol: ' + symbol)
    return int(hits[0], 16)
code_address = address('D3DDevice_BlockUntilIdle')
device_address = address('?smash_device@Fast@@3PAUD3DDevice@@A')
exe = xex.with_suffix('.exe').read_bytes()
pe = struct.unpack_from('<I', exe, 0x3c)[0]
sections = struct.unpack_from('<H', exe, pe + 6)[0]
opt_size = struct.unpack_from('<H', exe, pe + 20)[0]
image_base = struct.unpack_from('<I', exe, pe + 24 + 28)[0]
expected = None
for i in range(sections):
    offset = pe + 24 + opt_size + 40*i
    size, va, raw_size, raw = struct.unpack_from('<IIII', exe, offset + 8)
    rva = code_address - image_base
    if va <= rva < va + raw_size:
        expected = exe[raw + rva-va:raw + rva-va + 16]
if expected is None: raise ValueError('Function not in PE section')
k = c.WinDLL('kernel32', use_last_error=True)
k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]; k.OpenProcess.restype = w.HANDLE
k.ReadProcessMemory.argtypes = [w.HANDLE, w.LPCVOID, w.LPVOID, c.c_size_t, c.POINTER(c.c_size_t)]
k.ReadProcessMemory.restype = w.BOOL
k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)]
k.QueryFullProcessImageNameW.restype = w.BOOL
k.CloseHandle.argtypes = [w.HANDLE]
handle = k.OpenProcess(0x1000 | 0x10, False, launch['pid'])
if not handle: raise c.WinError(c.get_last_error())
def read(address, count):
    data = (c.c_ubyte * count)(); got = c.c_size_t()
    if not k.ReadProcessMemory(handle, c.c_void_p(address), data, count, c.byref(got)) or got.value != count:
        raise c.WinError(c.get_last_error())
    return bytes(data)
try:
    path = c.create_unicode_buffer(32768); length = w.DWORD(len(path))
    if not k.QueryFullProcessImageNameW(handle, 0, path, c.byref(length)): raise c.WinError(c.get_last_error())
    if Path(path.value).resolve() != (ROOT / 'scratch/xenia-emulator/xenia_canary.exe').resolve():
        raise ValueError('PID is not owned emulator')
    base = None
    for n in range(32, 48):
        candidate = 1 << n
        try:
            if read(candidate + code_address, 16) == expected: base = candidate; break
        except OSError: pass
    if base is None: raise ValueError('No verified guest mapping')
    device = int.from_bytes(read(base + device_address, 4), 'big')
    snapshot = read(base + device, 0x3600)
    # Xenia's E/F physical 4 KiB alias adds 0x1000 on hosts with 64 KiB
    # allocation granularity (memory.cc MapViews and host_address_offset).
    def guest_read(pointer, count):
        return read(base + pointer + (0x1000 if pointer >= 0xe0000000 else 0), count)
    pointees = {}
    for offset, count in [(0x2b10, 64), (0x2b14, 64), (0x2b4c, 256), (0x30, 32)]:
        pointer = int.from_bytes(snapshot[offset:offset+4], 'big')
        pointees[hex(offset)] = {'pointer': hex(pointer), 'bytes': guest_read(pointer, count).hex()}
    result = {'pid': launch['pid'], 'xex_sha256': launch['xex_sha256'],
              'mapping_base': hex(base), 'device_address': hex(device),
              'read_only': True, 'device_bytes': len(snapshot), 'pointees': pointees,
              'words': {hex(i): hex(int.from_bytes(snapshot[i:i+4], 'big'))
                        for i in [0x30, 0x38, 0x3520] + list(range(0x2b00, 0x2ba0, 4))}}
    (run / 'd3d-device.bin').write_bytes(snapshot)
    (run / 'd3d-device.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
finally:
    k.CloseHandle(handle)
