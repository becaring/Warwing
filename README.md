<picture>
  <source media="(prefers-color-scheme: light)" srcset="media/Warwing-on-light.svg">
  <img src="media/Warwing.svg" alt="Warwing" width="520">
</picture>

# Warwing

**Super Smash Bros. 64 on Xbox 360, powered by Shipyard.**

Warwing brings [BattleShip](https://github.com/JRickey/BattleShip), the native port of Super Smash Bros. 64, to Xbox 360. It runs at 1080p and 60 FPS. It builds its game data from your own ROM on first launch, so the release contains no Nintendo data.

## Requirements

- An Xbox 360 that runs homebrew, with Aurora, FSD or XeXMenu to launch XEX files.
- Your own **US v1.0** Super Smash Bros. ROM (`.z64`, `.n64` or `.v64`). Other regions and revisions won't work.
- A controller and a storage device for saves.

## Install

1. Download the release ZIP from [Releases](../../releases/latest), not GitHub's Source code ZIP.
2. Copy the `Warwing` folder to your console.
3. Put your ROM beside `Warwing.xex`.
4. Launch `Warwing.xex`. The first launch builds the game data from your ROM, and later launches reuse it.

## Controls

The game's controls can be remapped in the port's controller menu. Warwing adds:

| Input | Action |
|---|---|
| `Back` | Open or close the menu |
| Right stick | Move the menu cursor |
| `A` / `B` | Click or drag / right-click |
| `LT` / `RT` | Scroll |
| `R3` | Switch between the cursor and D-pad navigation |

### Known Limitations

- Tested on an RGH console. It should work on ABadAvatar, BadUpdate and PeerPressure consoles, but those haven't been tested.
- Singleplayer has been played through on hardware. Two controllers worked in a match with separate inputs, but multiplayer hasn't had longer playtesting.

## Logs

Warwing writes `warwing.log` beside `Warwing.xex`. Each launch is added to the end.

## Reporting a problem

Open a [bug report](../../issues/new/choose) and attach `warwing.log`. A report without a log and a description closes automatically and reopens when you add them.

## Support Me
[<img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" height="40">](https://buymeacoffee.com/becaring) [<img src="https://storage.ko-fi.com/cdn/kofi3.png?v=3" height="36">](https://ko-fi.com/becaring)

If you had fun with Warwing, a donation is NEVER required but always appreciated <3

## Building from Source

You need Windows, the Xbox 360 SDK, Visual Studio 2022 and a Shipyard checkout. [Building](docs/BUILDING.md) has the steps.

## Credits

Warwing builds on BattleShip, ssb-decomp-re, libultraship, Torch, Shipwright, SoH360 and [Shipyard](https://github.com/becaring/Shipyard).

Developed with AI coding assistants; design, integration and hardware validation by becaring.

## License

Original Warwing code is [MIT](LICENSE). Upstream components keep their own licenses; [Upstream](docs/UPSTREAM.md) lists them. Warwing is an unofficial fan project, unaffiliated with Nintendo, HAL Laboratory or Microsoft. The repository contains no ROMs or ROM-extracted retail game assets.
