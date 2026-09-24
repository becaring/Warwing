"""Generate XDK-compatible copies of hash-locked, actual LUS binarytools files.

Only explicitly listed whole-line edits are allowed. Algorithms remain upstream.
All inputs are validated and transformed in memory before any output is written.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE = resolve_platform_base(ROOT)
INPUTS = {
    'include/ship/utils/binarytools/BinaryWriter.h': '2d66b787bcb9eb624cc2c7db17256924c23c3fe15bbe61ad8de9bc6f00d71d00',
    'src/ship/utils/binarytools/BinaryWriter.cpp': '787f5955d06c683cc66dc6b75ed564876db7a299a6f7cc1931e70150e9ef8af3',
    'include/ship/utils/binarytools/BinaryReader.h': 'd701699033a16ebe5e3f90ae1867f52cd9744be6954ebf37148169a2b6129bfb',
    'include/ship/utils/binarytools/MemoryStream.h': 'f517ad9717472f09b85186e31d44a2c2450e97d2590b544bc6dee02bc5bb59b9',
    'include/ship/utils/binarytools/Stream.h': 'd8b3bc61f3ac9c348a2afee6e86b7570f40a04f00d199b80e61e7866f527ec1a',
    'include/ship/utils/binarytools/endianness.h': '7b00e7a299b17e65216c2c35a559547124e12a976367aba307169af228e94cdc',
    'src/ship/utils/binarytools/BinaryReader.cpp': 'f9238dfe70e0764f4db15f8dce9a522c8d05f330de504a41952801bb6988b61a',
    'src/ship/utils/binarytools/MemoryStream.cpp': '6f38568249786547af09c2775b99aec5c9ce8ab34d28bd9dce076eafbc24b96f',
    'src/ship/utils/binarytools/Stream.cpp': '46449a6de77cb7c0ae1f64099b195ae4b00ef78dddfb24c3a43e7cc7ea627130',
}
NATIVE_CONDITION = '#if (defined(__BYTE_ORDER__) && (__BYTE_ORDER__ == __ORDER_BIG_ENDIAN__)) || defined(__BIG_ENDIAN__)\n'
XDK_NATIVE_CONDITION = '#if (defined(_XBOX) && defined(_M_PPC)) || (defined(__BYTE_ORDER__) && (__BYTE_ORDER__ == __ORDER_BIG_ENDIAN__)) || defined(__BIG_ENDIAN__)\n'


class Edits:
    def __init__(self, text, path):
        self.text, self.path, self.edits = text, path, []

    def exact(self, before, after, count=1):
        if self.text.count(before) != count:
            raise ValueError(f'{self.path}: expected {count} occurrences of {before!r}')
        if not before.endswith('\n') or not after.endswith('\n'):
            raise ValueError('edits must end at line boundaries')
        pos = 0
        for _ in range(count):
            start = self.text.index(before, pos)
            if start and self.text[start - 1] != '\n':
                raise ValueError('edits must begin at line boundaries')
            end = start + len(before)
            self.edits.append((start, end, after))
            pos = end

    def render(self):
        path = self.path.as_posix().replace('"', '\\"')
        output = ['// Generated from hash-locked LUS source; do not edit.\n']
        guard = 'SMASH360_GENERATED_BINARYTOOLS_' + self.path.name.upper().replace('.', '_')
        if self.path.suffix == '.h':
            # XDK does not reliably deduplicate #pragma once after #line remaps
            # the header filename. A physical-file guard precedes the mapping.
            output.append(f'#ifndef {guard}\n#define {guard}\n')
        output.append(f'#line 1 "{path}"\n')
        cursor = 0
        for start, end, replacement in sorted(self.edits):
            if start < cursor:
                raise ValueError(f'{self.path}: overlapping transformations')
            output.append(self.text[cursor:start])
            output.append(replacement)
            output.append(f'#line {self.text.count(chr(10), 0, end) + 1} "{path}"\n')
            cursor = end
        output.append(self.text[cursor:])
        if self.path.suffix == '.h':
            output.append(f'\n#endif // {guard}\n')
        return ''.join(output).encode('utf-8')


def strong_enum(name, body):
    return (f'struct {name} : public Shipyard::Binary::ScopedEnum<{name}> {{\n'
            f'    enum Value {{{body}\n    }};\n'
            f'    {name}() {{}}\n'
            f'    {name}(Value value) : Shipyard::Binary::ScopedEnum<{name}>(value) {{}}\n'
            f'    explicit {name}(int value) : Shipyard::Binary::ScopedEnum<{name}>(value) {{}}\n'
            '};\n')


def transform(relative, raw, path):
    text = raw.decode('utf-8').replace('\r\n', '\n')
    edits = Edits(text, path)
    if relative.endswith('/endianness.h'):
        original = ('enum class Endianness {\n    Little = 0,\n    Big = 1,\n\n' + NATIVE_CONDITION +
                    '    Native = Big,\n#else\n    Native = Little,\n#endif\n};\n')
        body = '\n    Little = 0,\n    Big = 1,\n\n' + XDK_NATIVE_CONDITION + '    Native = Big,\n#else\n    Native = Little,\n#endif'
        edits.exact(original, strong_enum('Endianness', body))
        edits.exact('#ifdef __cplusplus\n', '#ifdef __cplusplus\n#include "binary/compat.h"\n')
        # The second endian condition controls BE/LE swap macros, outside the enum.
        before = NATIVE_CONDITION + '#ifndef IS_BIGENDIAN\n'
        edits.exact(before, XDK_NATIVE_CONDITION + '#ifndef IS_BIGENDIAN\n')
    elif relative.endswith('/Stream.h'):
        edits.exact('#include <vector>\n', '#include <vector>\n#include "binary/compat.h"\n')
        edits.exact('enum class SeekOffsetType { Start, Current, End };\n',
                    strong_enum('SeekOffsetType', ' Start, Current, End'))
        edits.exact('    virtual ~Stream() = default;\n', '    virtual ~Stream() {}\n')
    elif relative.endswith('/MemoryStream.h'):
        edits.exact('class MemoryStream final : public Stream {\n', 'class MemoryStream : public Stream {\n')
        lines = [line for line in text.splitlines(keepends=True) if ' override;' in line]
        if len(lines) != 10:
            raise ValueError('unexpected MemoryStream override declarations')
        for line in lines:
            edits.exact(line, line.replace(' override;', ';'))
    elif relative.endswith(('/BinaryReader.h','/BinaryWriter.h')):
        edits.exact('    Endianness mEndianness = Endianness::Native;\n', '    Endianness mEndianness;\n')
    elif relative.endswith('/BinaryWriter.cpp'):
        for signature in ('', 'Stream* nStream', 'std::shared_ptr<Stream> nStream'):
            before = f'Ship::BinaryWriter::BinaryWriter({signature}) {{\n'
            edits.exact(before, f'Ship::BinaryWriter::BinaryWriter({signature}) : mEndianness(Endianness::Native) {{\n')
        edits.exact('    for (char c : str) {\n', '    for (std::string::const_iterator i = str.begin(), end = str.end(); i != end; ++i) {\n        char c = *i;\n')
    elif relative.endswith('/BinaryReader.cpp'):
        for signature in ('char* nBuffer, size_t nBufferSize', 'Stream* nStream', 'std::shared_ptr<Stream> nStream'):
            before = f'Ship::BinaryReader::BinaryReader({signature}) {{\n'
            edits.exact(before, f'Ship::BinaryReader::BinaryReader({signature}) : mEndianness(Endianness::Native) {{\n')
        edits.exact('    float result = NAN;\n', '    float result = Shipyard::Binary::QuietNaN();\n')
        edits.exact('    double result = NAN;\n', '    double result = Shipyard::Binary::QuietNaN();\n')
        edits.exact('    if (std::isnan(result)) {\n', '    if (Shipyard::Binary::IsNaN(result)) {\n', 2)
    elif relative.endswith('/MemoryStream.cpp'):
        default_body = ('    mBuffer = std::make_shared<std::vector<char>>();\n'
                        '    // mBuffer.reserve(1024 * 16);\n'
                        '    mBufferSize = 0;\n    mBaseAddress = 0;\n')
        if f'Ship::MemoryStream::MemoryStream() {{\n{default_body}}}\n' not in text:
            raise ValueError('default MemoryStream constructor changed')
        for signature in ('char* nBuffer, size_t nBufferSize', 'std::shared_ptr<std::vector<char>> buffer',
                          'std::shared_ptr<std::vector<char>> buffer, size_t offset'):
            before = f'Ship::MemoryStream::MemoryStream({signature}) : MemoryStream() {{\n'
            # Exact original default body executes before the original delegating
            # constructor body, including the temporary empty-buffer allocation.
            edits.exact(before, f'Ship::MemoryStream::MemoryStream({signature}) {{\n' + default_body)
        edits.exact('    std::unique_ptr<char[]> result = std::make_unique<char[]>(length);\n',
                    '    std::unique_ptr<char[]> result = Shipyard::Binary::MakeZeroedChars(length);\n')
    elif not relative.endswith('/Stream.cpp'):
        raise ValueError(f'unrecognized input {relative}')
    return edits.render(), len(edits.edits)


def generate(source, destination):
    source, destination = source.resolve(), destination.resolve()
    if not destination.is_relative_to(ROOT / 'scratch/binary-reader-xdk'):
        raise ValueError('output must remain under scratch/binary-reader-xdk')
    prepared = []
    for relative, expected in INPUTS.items():
        path = source / relative
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected:
            raise ValueError(f'{relative}: source SHA-256 mismatch: expected {expected}, got {actual}')
        output, edit_count = transform(relative, raw, path)
        prepared.append((relative, output, {'input_sha256': actual,
                         'output_sha256': hashlib.sha256(output).hexdigest(), 'edits': edit_count}))
    helper = PLATFORM_BASE / 'sources/binary/compat.h'
    manifest = {'source': str(source), 'libultraship_commit': '89d9de83a8d09bd7d3b7bc7f8d08554ee2ce8459',
                'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'helper_sha256': hashlib.sha256(helper.read_bytes()).hexdigest(),
                'compat_header_source': 'platform_base:sources/binary/compat.h', 'files': {}}
    for relative, output, metadata in prepared:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(output)
        manifest['files'][relative] = metadata
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'upstream/BattleShip/libultraship')
    parser.add_argument('--output', type=Path, default=ROOT / 'scratch/binary-reader-xdk/generated')
    args = parser.parse_args()
    result = generate(args.source, args.output)
    print(f'Generated {len(result["files"])} pinned LUS binarytools files')


if __name__ == '__main__':
    main()
