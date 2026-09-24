"""Verify the real linked XDK RDP allocation, zeroing and construction order.

This is deliberately a small, fail-closed PPC data-flow check, not a general
disassembler. It follows the successful allocation paths in the emitted helper.
A host compiler
test cannot detect the XDK's missing value-initialization of this non-POD type.
No title code or input binary is changed. JSON and disassembly are evidence only.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "scratch/application-xdk/native/build"
DEFAULT_DUMPBIN = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK/bin/win32/dumpbin.exe")
INTERPRETER = "??0Interpreter@Fast@@QAA@XZ"
RDP = "??0RDP@Fast@@QAA@XZ"
NEW = "??2@YAPAXI@Z"
HELPER_PREFIX = "??$NewValueInitialized@URDP@Fast@@@Fast3D@Shipyard@@"


class VerificationError(RuntimeError):
    pass


def need(condition, message):
    if not condition:
        raise VerificationError(message)


def symbols_from_map(path):
    result = {}
    for line in path.read_text().splitlines():
        match = re.match(r"\s*[0-9A-Fa-f]+:[0-9A-Fa-f]+\s+(\S+)\s+([0-9A-Fa-f]{8})\s+f(?:\s|$)", line)
        if match:
            name, address = match[1], int(match[2], 16)
            if name in result and result[name] != address:
                need(name not in (INTERPRETER, RDP, NEW, "memset") and not name.startswith(HELPER_PREFIX),
                     "Ambiguous required map symbol: " + name)
                # Translation-local generated functions can share decorated
                # names. Keep their address for bounding, never for resolution.
                name += "@map-address-%08x" % address
            result[name] = address
    for name in (INTERPRETER, RDP, NEW, "memset"):
        need(name in result, "Missing required linked symbol: " + name)
    return result


def dump_function(exe, dumpbin, symbols, name):
    start = symbols[name]
    following = sorted({v for v in symbols.values() if v > start})
    need(bool(following), "Cannot bound linked function " + name)
    end = following[0]
    need(end - start < 65536, "Unexpected function extent for " + name)
    command = [str(dumpbin), "/disasm", "/range:0x%x,0x%x" % (start, end - 1), str(exe)]
    process = subprocess.run(command, capture_output=True, text=True, errors="replace")
    need(process.returncode == 0, "dumpbin failed: " + process.stdout + process.stderr)
    instructions = []
    for line in process.stdout.splitlines():
        match = re.match(r"\s*([0-9A-Fa-f]{8}):\s+([0-9A-Fa-f]{8})\s+(\S+)\s*(.*)", line)
        if match:
            instructions.append((int(match[1], 16), match[3], match[4].split(";", 1)[0].strip()))
    need(instructions and instructions[0][0] == start, "No PPC instructions at function start: " + name)
    return process.stdout + process.stderr, instructions


def number(value):
    value = value.strip()
    if value.lower().endswith("h"):
        return int(value[:-1], 16)
    return int(value, 0)


def add(value, offset):
    if isinstance(value, int):
        return value + offset
    if isinstance(value, tuple) and value[0] == "stack":
        return ("stack", value[1] + offset)
    if isinstance(value, tuple) and value[0] == "allocation" and offset:
        return ("allocation_offset", value[1], value[2], offset)
    if isinstance(value, tuple) and value[0] == "allocation_offset":
        return ("allocation_offset", value[1], value[2], value[3] + offset)
    if offset == 0:
        return value
    return None


def branch_target(operand, symbols):
    target = operand.split(",")[-1].strip()
    if re.fullmatch(r"[0-9A-Fa-f]{8}", target):
        return int(target, 16)
    return symbols.get(target)


def allocated(value):
    return isinstance(value, tuple) and value[0] == "allocation"


def prove_chain(instructions, symbols):
    by_address = {row[0]: row for row in instructions}
    # Constructor member initialization precedes its explicit heap allocations.
    # Start at the RDP allocation's literal size load, not unrelated container
    # initialization loops. All later branches and the target constructor remain
    # inside the checked slice. Reject a changed/nonliteral size setup.
    constructors = [i for i, row in enumerate(instructions)
                    if row[1] == "bl" and branch_target(row[2], symbols) == symbols[RDP]]
    need(len(constructors) == 1, "Expected exactly one direct RDP constructor call in checked function")
    allocation = next((i for i in range(constructors[0] - 1, -1, -1)
                       if instructions[i][1] == "bl" and branch_target(instructions[i][2], symbols) == symbols[NEW]), None)
    need(allocation is not None, "No direct global operator-new call before RDP construction")
    begin = next((i for i in range(allocation - 1, max(-1, allocation - 12), -1)
                  if instructions[i][1] == "li" and instructions[i][2].split(",")[0].strip() == "r3"), None)
    need(begin is not None, "No bounded literal allocation-size setup")
    need(not any(row[1].startswith("b") for row in instructions[begin:allocation]),
         "Allocation-size setup contains unexpected control flow")
    stack_regs = {"r1": ("stack", 0)}
    for _, opcode, operands in instructions[:begin]:
        parts = [p.strip() for p in operands.split(",")]
        if opcode == "addi" and parts[1] in stack_regs:
            stack_regs[parts[0]] = add(stack_regs[parts[1]], number(parts[2]))
        elif opcode in ("stwu", "stdu") and parts[0] == "r1":
            match = re.fullmatch(r"([^()]+)\(r1\)", parts[1])
            need(match is not None, "Unsupported stack prologue")
            stack_regs["r1"] = add(stack_regs["r1"], number(match[1]))
    # Values are integer constants, symbolic stack addresses, or exact allocation
    # identities. Volatile registers are killed at every ordinary function call.
    queue = [(instructions[begin][0], stack_regs, {}, {}, {}, [], 0)]
    proofs = []
    explored = 0
    while queue:
        pc, regs, memory, comparisons, cleared, events, steps = queue.pop()
        while pc in by_address:
            steps += 1
            explored += 1
            need(steps < 4096 and explored < 32768, "Unexpected loop or excessive PPC control flow")
            address, opcode, operands = by_address[pc]
            parts = [p.strip() for p in operands.split(",")]
            next_pc = pc + 4
            if opcode == "bl":
                target = branch_target(operands, symbols)
                if target == symbols[RDP]:
                    pointer = regs.get("r3")
                    need(allocated(pointer), "RDP constructor destination is not a proven operator-new allocation at 0x%x" % pc)
                    allocation_pc, size = pointer[1], pointer[2]
                    need(allocation_pc in cleared,
                         "RDP constructor at 0x%x receives %d-byte allocation from 0x%x without complete zeroing" % (pc, size, allocation_pc))
                    zero_pc = cleared[allocation_pc]
                    proofs.append({"allocation_address": "0x%08X" % allocation_pc,
                                   "allocation_bytes": size, "memset_address": "0x%08X" % zero_pc,
                                   "constructor_address": "0x%08X" % pc,
                                   "same_destination": True, "events": events})
                    # Constructor internals and exception cleanup are outside this
                    # narrow contract; the actual target symbol is checked above.
                    break
                argument3, argument4, argument5 = (regs.get("r%d" % i) for i in (3, 4, 5))
                for i in range(0, 13):
                    if i != 1:
                        regs.pop("r%d" % i, None)
                comparisons.clear()
                if target == symbols[NEW]:
                    need(isinstance(argument3, int) and 0 < argument3 < 1024 * 1024,
                         "Cannot derive operator-new allocation size at 0x%x" % pc)
                    regs["r3"] = ("allocation", pc, argument3)
                    events.append({"call": "operator new", "address": "0x%08X" % pc, "bytes": argument3})
                elif target == symbols["memset"]:
                    if allocated(argument3):
                        need(argument4 == 0, "Allocation memset is not proven zero at 0x%x" % pc)
                        need(argument5 == argument3[2], "Allocation memset does not cover the exact full allocation at 0x%x" % pc)
                        cleared[argument3[1]] = pc
                        events.append({"call": "memset", "address": "0x%08X" % pc, "bytes": argument5, "value": 0})
                    regs["r3"] = argument3
                else:
                    raise VerificationError("Unverified function call between RDP allocation and construction at 0x%x" % pc)
            elif opcode == "blr" or opcode == "bctr":
                break
            elif opcode in ("b", "ba"):
                next_pc = branch_target(operands, symbols)
                need(next_pc in by_address, "Unexpected tail branch before proven construction at 0x%x" % pc)
            elif opcode in ("beq", "bne"):
                condition_register = parts[0] if len(parts) == 2 else "cr0"
                condition = comparisons.get(condition_register)
                take = condition if opcode == "beq" else (None if condition is None else not condition)
                target = branch_target(operands, symbols)
                need(target in by_address, "Conditional branch escapes function at 0x%x" % pc)
                if take is None:
                    queue.append((target, copy.copy(regs), copy.copy(memory), copy.copy(comparisons),
                                  copy.copy(cleared), copy.deepcopy(events), steps))
                elif take:
                    next_pc = target
            elif opcode.startswith("b"):
                # Do not guess conditions, indirect calls, loops or branch forms.
                raise VerificationError("Unsupported PPC branch before construction: 0x%x %s %s" % (pc, opcode, operands))
            elif opcode in ("cmpwi", "cmplwi", "cmpdi", "cmpldi"):
                condition_register, source, immediate = parts if len(parts) == 3 else ["cr0"] + parts
                value, immediate = regs.get(source), number(immediate)
                comparisons[condition_register] = (value == immediate if isinstance(value, int)
                    else False if allocated(value) and immediate == 0 else None)
            elif opcode == "li":
                regs[parts[0]] = number(parts[1])
            elif opcode == "lis":
                regs[parts[0]] = number(parts[1]) << 16
            elif opcode == "mr":
                regs[parts[0]] = regs.get(parts[1])
            elif opcode == "addi":
                regs[parts[0]] = add(regs.get(parts[1]), number(parts[2]))
            elif opcode in ("ori", "oris"):
                source = regs.get(parts[1])
                regs[parts[0]] = (source | (number(parts[2]) << (16 if opcode == "oris" else 0))) if isinstance(source, int) else None
            elif opcode in ("stw", "std", "stwu", "stdu", "lwz", "ld", "lwzu", "ldu"):
                match = re.fullmatch(r"([^()]+)\((r\d+)\)", parts[1])
                need(match is not None, "Unrecognized PPC memory operand at 0x%x" % pc)
                location = add(regs.get(match[2]), number(match[1]))
                if opcode.startswith("st"):
                    need(isinstance(location, tuple) and location[0] == "stack",
                         "Non-stack write between RDP allocation and construction at 0x%x" % pc)
                    memory[location] = regs.get(parts[0])
                else:
                    regs[parts[0]] = memory.get(location)
                if opcode.endswith("u"):
                    regs[match[2]] = location
            elif opcode == "nop" or opcode.startswith("mt"):
                pass
            elif opcode.startswith("st"):
                raise VerificationError("Unverified memory write before RDP construction at 0x%x" % pc)
            else:
                raise VerificationError("Unsupported instruction in RDP allocation chain: 0x%x %s %s" % (pc, opcode, operands))
            pc = next_pc
    need(proofs, "No reachable complete RDP construction chain was proven")
    # Branch joins can visit the same call twice; retain one identical receipt.
    return list({json.dumps(proof, sort_keys=True): proof for proof in proofs}.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=BUILD / "Smash360.exe")
    parser.add_argument("--map", type=Path, default=BUILD / "Smash360.map")
    parser.add_argument("--dumpbin", type=Path, default=DEFAULT_DUMPBIN)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "scratch/evidence/rdp-value-init")
    parser.add_argument("--label", default="current")
    args = parser.parse_args()
    need(re.fullmatch(r"[A-Za-z0-9_-]+", args.label), "Invalid evidence label")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    receipt = {"status": "FAIL", "scope": "Linked PPC RDP allocation/value-initialization order only; not visible-rendering proof",
               "exe": str(args.exe.resolve()), "map": str(args.map.resolve())}
    try:
        receipt["exe_sha256"] = hashlib.sha256(args.exe.read_bytes()).hexdigest()
        receipt["map_sha256"] = hashlib.sha256(args.map.read_bytes()).hexdigest()
        symbols = symbols_from_map(args.map)
        helpers = [name for name in symbols if name.startswith(HELPER_PREFIX)]
        need(len(helpers) == 1, "Expected one linked Shipyard RDP value-initialization specialization")
        scope = helpers[0]
        receipt["checked_function"] = scope
        all_instructions = {}
        for label, name in (("allocation", scope), ("rdp-constructor", RDP), ("interpreter", INTERPRETER)):
            text, instructions = dump_function(args.exe, args.dumpbin, symbols, name)
            (args.output_dir / (args.label + "-" + label + ".disasm.txt")).write_text(text)
            all_instructions[label] = instructions
        calls = ["0x%08X" % address for address, opcode, operands in all_instructions["interpreter"]
                 if opcode == "bl" and branch_target(operands, symbols) == symbols[scope]]
        need(len(calls) == 1, "Production Interpreter must call the verified Shipyard helper exactly once")
        receipt["production_helper_call"] = calls[0]
        receipt["proofs"] = prove_chain(all_instructions["allocation"], symbols)
        receipt["status"] = "PASS"
    except (VerificationError, OSError, subprocess.SubprocessError, ValueError) as error:
        receipt["error"] = str(error)
    path = args.output_dir / (args.label + "-verification.json")
    path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    print("Evidence: " + str(path))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
