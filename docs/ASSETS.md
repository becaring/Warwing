# Assets

Supply your own supported US Super Smash Bros. ROM. The extraction script
validates the ROM and normalizes its byte order. ROMs and extracted data are
not included in this repository.

After fetching the sources and dependencies in [Building](BUILDING.md), run:

```powershell
./tools/build-assets.ps1 -Rom './Super Smash Bros. (USA).n64'
```

The script builds pinned Torch on the PC and extracts `BattleShip.o2r` and
`f3d.o2r`. Keep both required archives beside the packaged `Smash360.xex`.
Use the archives produced for the selected source revisions. Keep ROMs,
extracted archives, and local game packages outside source control.
