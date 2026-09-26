# Upstream and provenance

Warwing integrates [BattleShip](https://github.com/JRickey/BattleShip), including
its selected [ssb-decomp-re](https://github.com/JRickey/ssb-decomp-re),
[libultraship/Fast3D](https://github.com/JRickey/libultraship), and
[Torch](https://github.com/JRickey/Torch) submodules. BattleShip's source and
asset-extraction pipeline remain authoritative for Smash behavior and data.
The Xbox integration uses [Shipyard](https://github.com/becaring/Shipyard), with
platform ancestry from SoH360 and Shipwright.

## Reproducible inputs

| Input | Authority |
| --- | --- |
| BattleShip and its submodules | `tools/fetch-sources.ps1` and `tools/audit_sources.py` |
| External dependencies | `dependencies.lock.json` |
| Shared Xbox platform | `platform-base.lock.json` |
| Adapted subsystem inputs | Source locks under `platform/xbox360` |
| Imported platform material | Source copyright notices, source locks, and donor provenance records |
| Emitted compiler inputs | Generated manifests, hashes, and source-line mappings |

The fetched upstream trees live under `upstream/` and are not maintained by
editing the generated build tree. A source update requires reviewing changed
contracts, updating exact locks, regenerating, and rerunning the affected
comparisons and native build. Do not lower upstream versions merely to silence
compiler errors or replace a current interface with an older donor interface.

A consumer can intentionally select an older Shipyard revision. Shared changes
are integrated into one canonical Shipyard history; consumers adopt a reviewed
revision explicitly. Do not copy a second private platform implementation into
the consumer to bypass a pin or contract.

## Licenses and credits

Preserve all applicable copyright notices, license texts, attribution, and
source provenance when adapting code. The dependency repositories and selected
revisions define their own license terms; this document does not assign a new
license to their code. In particular, retain the nlohmann JSON MIT notice at
`platform/xbox360/cpp-compat/json/LICENSE.nlohmann.MIT` and the donor provenance
at `platform/xbox360/game-compat/donor/provenance.json`, together with all source
locks and notices embedded in maintained files.

Thanks to the BattleShip, ssb-decomp-re, libultraship/Fast3D, Torch, Shipwright,
SoH360, Shipyard, and third-party dependency contributors. Game names and assets
remain the property of their respective rights holders. Builders supply their
own game data and SDK; neither is part of this repository.
