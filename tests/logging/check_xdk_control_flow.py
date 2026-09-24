"""Check the real logger's linked PPC normal flow cannot enter EH metadata.

This is a targeted regression for XDK 21256 /O2 omitting the branch after
backend_flush_. It inspects production EXE/MAP bytes, not a surrogate logger.
Calls are assumed to return; exception dispatch itself is outside this check.
"""
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
SYMBOL = '?backend_sink_it_@async_logger@spdlog@@IAAXABUlog_msg@details@2@@Z'


def check(exe_path):
    symbols = [(name, int(address, 16)) for name, address in re.findall(
        r'^\s*\w+:\w+\s+(\S+)\s+([0-9a-fA-F]{8})\s+f\s',
        exe_path.with_suffix('.map').read_text(), re.M)]
    starts = {address for name, address in symbols if name == SYMBOL}
    if len(starts) != 1:
        raise ValueError('Expected one real async logger sink function')
    start = starts.pop()
    end = min(address for name, address in symbols
              if address > start and not name.startswith('__'))
    catches = {address for name, address in symbols
               if name.startswith('__catch$') and start < address < end}
    if not catches:
        raise ValueError('Expected retained exception handlers in real logger')
    forbidden = {a + delta for a in catches for delta in (-8, -4, 0)}
    data = exe_path.read_bytes()
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    count, opt = struct.unpack_from('<H', data, pe+6)[0], struct.unpack_from('<H', data, pe+20)[0]
    base = struct.unpack_from('<I', data, pe+52)[0]
    sections = [struct.unpack_from('<IIII', data, pe+24+opt+i*40+8) for i in range(count)]

    def word(pc):
        for size, va, raw_size, raw in sections:
            if va <= pc-base < va+raw_size:
                return struct.unpack_from('>I', data, raw+pc-base-va)[0]
        raise ValueError('Instruction outside PE sections')

    def signed(value, width):
        return (value ^ (1 << (width-1))) - (1 << (width-1))

    pending, visited = [start], set()
    while pending:
        pc = pending.pop()
        if pc in visited:
            continue
        if pc in forbidden:
            raise ValueError(f'Normal logger flow reaches exception metadata at {pc:08X}')
        if not start <= pc < end:
            continue  # Tail-call / epilog helper outside this function.
        visited.add(pc)
        instruction = word(pc)
        opcode = instruction >> 26
        if opcode in (16, 18):
            if instruction & 1:  # Linked branch: inspect return path.
                pending.append(pc+4)
                continue
            mask, width = (0xfffc, 16) if opcode == 16 else (0x3fffffc, 26)
            target = signed(instruction & mask, width)
            pending.append(target if instruction & 2 else pc+target)
            if opcode == 16:
                pending.append(pc+4)
        elif opcode == 19 and ((instruction >> 1) & 1023) in (16, 528):
            if instruction & 1 or ((instruction >> 21) & 20) != 20:
                pending.append(pc+4)
        else:
            pending.append(pc+4)
    print(f'PASS real PPC logger normal control flow: {len(visited)} instructions; {len(catches)} EH handlers retained')


if __name__ == '__main__':
    check(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT/'scratch/application-xdk/native/build/Smash360.exe')
