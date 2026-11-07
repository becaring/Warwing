"""Check the console ROM extractor's entry table against the pinned Torch YAMLs without a ROM."""

from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rom_entries


def main():
    rows = rom_entries.entries()
    relocs = [row for row in rows if row[1] >= 0]
    blobs = [row for row in rows if row[1] < 0]
    assert (len(relocs), len(blobs)) == (2132, 26), (len(relocs), len(blobs))
    assert sorted(row[1] for row in relocs) == list(range(2132))
    assert all(offset + size <= 0x1000000 and size for _, _, offset, size in blobs)
    with tempfile.TemporaryDirectory() as name:
        out = Path(name) / "rom_entries.cpp"
        assert rom_entries.generate(out) == len(rows)
        text = out.read_text(encoding="utf-8")
        assert text.count("\n    { ") == len(rows) and "\r" not in text
    print("ROM entry table: %d reloc files, %d blobs" % (len(relocs), len(blobs)))


if __name__ == "__main__":
    main()
