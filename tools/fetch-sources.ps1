$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$target = Join-Path $root 'upstream\BattleShip'
$revision = '07d04c5a8d3b1b712e2a749cbdd3812588bdb756'
$gitSafety = @()
foreach ($relative in @('', 'decomp', 'libultraship', 'torch')) {
    $safePath = if ($relative) { Join-Path $target $relative } else { $target }
    $gitSafety += @('-c', ('safe.directory=' + $safePath.Replace('\','/')))
}
# Git's shell-based submodule helper needs its bundled Unix utilities on PATH.
$gitExe = (Get-Command git -ErrorAction Stop).Source
$gitRoot = Split-Path (Split-Path $gitExe -Parent) -Parent
foreach ($candidate in @($gitRoot, 'C:\Program Files\Git')) {
    $gitUsr = Join-Path $candidate 'usr\bin'
    if (Test-Path -LiteralPath (Join-Path $gitUsr 'sed.exe')) {
        $env:PATH = $gitUsr + ';' + (Join-Path $candidate 'mingw64\bin') + ';' + $env:PATH
        break
    }
}
if (!(Test-Path -LiteralPath $target)) {
    & git @gitSafety clone 'https://github.com/JRickey/BattleShip.git' $target
    if ($LASTEXITCODE -ne 0) { throw 'BattleShip clone failed' }
}
$dirty = & git @gitSafety -C $target status --porcelain
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect BattleShip checkout' }
if ($dirty) { throw 'Checkout has local changes; refusing to replace them' }
& git @gitSafety -C $target cat-file -e ($revision + '^{commit}')
if ($LASTEXITCODE -ne 0) {
    & git @gitSafety -C $target fetch origin $revision
    if ($LASTEXITCODE -ne 0) { throw 'Cannot fetch pinned BattleShip revision' }
}
& git @gitSafety -C $target checkout --detach $revision
if ($LASTEXITCODE -ne 0) { throw 'Cannot select pinned BattleShip revision' }
& git @gitSafety -C $target submodule update --init --recursive
if ($LASTEXITCODE -ne 0) { throw 'Pinned submodule acquisition failed' }
& python -B (Join-Path $PSScriptRoot 'audit_sources.py')
if ($LASTEXITCODE -ne 0) { throw 'Source audit failed' }
