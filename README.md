# Warwing

**Super Smash Bros. 64 on Xbox 360, powered by Shipyard.**

Warwing runs [BattleShip](https://github.com/JRickey/BattleShip), the native port of Super Smash Bros. for Nintendo 64, on Xbox 360 hardware. It runs at 1080p and 60 FPS, draws with the console's GPU and plays audio through XAudio2. Warwing builds its game data from your own ROM the first time it starts, so the release contains no Nintendo data.

## Requirements

- An Xbox 360 that can run homebrew, with a dashboard or file manager that launches XEX files (Aurora, FSD or XeXMenu).
- Your own **US v1.0** Super Smash Bros. ROM as a `.z64`, `.n64` or `.v64` file. Other regions and revisions are not supported.
- A controller. Native keyboard input and Raphnet USB adapters are not supported.
- A storage device for saves. On first start Warwing asks which one to use and creates a 1 MiB save container there.

## Install

1. Download the latest Warwing release ZIP from [Releases](../../releases/latest), not GitHub's Source code ZIP.
2. Copy the `Warwing` folder from the ZIP to your console over FTP or with a USB drive.
3. Put your ROM in that folder, beside `Warwing.xex`.
4. Launch `Warwing.xex`. The first launch builds `BattleShip.o2r` from the ROM and saves it in the same folder; later launches reuse it.

## Controls

The game uses Super Smash Bros.' own controls, and you can remap them in the port's controller menu. Warwing adds:

| Input | Action |
|---|---|
| `Back` | Open or close the enhancement menu |
| Right stick | Move the menu cursor |
| `A` / `B` | Click or drag / right-click |
| `LT` / `RT` | Scroll |
| `R3` | Switch between the cursor and D-pad navigation |

### Known Limitations

- Tested on an RGH console. It should work on ABadAvatar, BadUpdate and PeerPressure consoles, but those haven't been tested.
- Singleplayer has been played through on hardware. A match with two controllers worked, each with its own inputs, but multiplayer hasn't had longer playtesting yet.

## Logs

Warwing writes everything to `warwing.log` in its folder, beside `Warwing.xex`. The log keeps every launch, with the latest run at the end.

## Reporting a problem

Open a [bug report](../../issues/new/choose) and attach `warwing.log`. A report without a log file and a description of what happened closes automatically, and it reopens when you edit it to add them.

## Support Me
[<img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" height="40">](https://buymeacoffee.com/becaring) [<img src="https://storage.ko-fi.com/cdn/kofi3.png?v=3" height="36">](https://ko-fi.com/becaring)

If you had fun with Warwing, a donation is NEVER required but always appreciated <3

## Building from Source

You need Windows, the Xbox 360 SDK, Visual Studio 2022 and a Shipyard checkout. [Building](docs/BUILDING.md) has the steps, [Assets](docs/ASSETS.md) covers the ROM and packaging, and [Architecture](docs/ARCHITECTURE.md) and [Upstream](docs/UPSTREAM.md) describe how the port fits together.

## Credits

Warwing builds on BattleShip, ssb-decomp-re, libultraship/Fast3D, Torch, Shipwright and SoH360, and on [Shipyard](https://github.com/becaring/Shipyard) for its Xbox 360 platform code. Thanks to everyone who worked on them.

Developed with AI coding assistants; design, integration and hardware validation by becaring.

## License

Original Warwing code is [MIT](LICENSE). Upstream components keep their own licenses and notices; [Upstream](docs/UPSTREAM.md) lists them. Warwing is an unofficial fan project, unaffiliated with Nintendo, HAL Laboratory or Microsoft. The repository and releases contain no ROMs, game assets or Xbox 360 SDK files; supply your own ROM.
