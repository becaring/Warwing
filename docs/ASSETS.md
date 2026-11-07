# Assets

You need your own supported US Super Smash Bros. ROM. The extraction script
validates the ROM and normalizes its byte order. This repository contains
neither ROMs nor extracted data.

After fetching the sources and dependencies in [Building](BUILDING.md), run:

```powershell
./tools/build-assets.ps1 -Rom './Super Smash Bros. (USA).n64'
```

The script builds pinned Torch on the PC and extracts `BattleShip.o2r` and
`f3d.o2r`. `f3d.o2r` holds only shaders and ships beside `Warwing.xex`.
`BattleShip.o2r` holds ROM data and never ships: when it is missing, the XEX
builds it from a US v1.0 ROM beside it, byte for byte the same as Torch.
`tools/check_rom_archive.py <ROM folder>` checks that match on the PC. Keep
ROMs, extracted archives, and local game packages out of source control.
