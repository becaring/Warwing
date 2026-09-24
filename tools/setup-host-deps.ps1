$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$target = Join-Path $root 'scratch/host-python'
# Dependency of the original BattleShip CSS PNG/header generators only.
& python -m pip install --disable-pip-version-check --no-cache-dir --target $target 'Pillow==11.3.0' 'tree-sitter==0.25.2' 'tree-sitter-cpp==0.23.4'
if ($LASTEXITCODE -ne 0) { throw 'Pinned host asset dependency installation failed' }
$smashParserTarget = Join-Path $root 'scratch/game-xdk/python-tools'
& python -m pip install --disable-pip-version-check --no-cache-dir --target $smashParserTarget 'tree-sitter==0.25.2' 'tree-sitter-c==0.24.1'
if ($LASTEXITCODE -ne 0) { throw 'Pinned C projection parser installation failed' }
