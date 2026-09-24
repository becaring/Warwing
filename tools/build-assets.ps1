param([string]$Rom = 'Super Smash Bros. (USA).n64')
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (![IO.Path]::IsPathRooted($Rom)) { $Rom = Join-Path $root $Rom }
& python -B (Join-Path $PSScriptRoot 'normalize_rom.py') $Rom
if ($LASTEXITCODE -ne 0) { throw 'ROM validation failed' }
& python -B (Join-Path $PSScriptRoot 'audit_sources.py')
if ($LASTEXITCODE -ne 0) { throw 'Source validation failed' }
$build = Join-Path $root 'scratch/torch-host'
$logs = Join-Path $root 'scratch/logs'
New-Item -ItemType Directory -Force $logs | Out-Null
# Git FetchContent needs the shell helpers shipped with Git for Windows.
$gitExe = (Get-Command git -ErrorAction Stop).Source
$gitRoot = Split-Path (Split-Path $gitExe -Parent) -Parent
foreach ($candidate in @($gitRoot, 'C:/Program Files/Git')) {
    if (Test-Path -LiteralPath (Join-Path $candidate 'usr/bin/sed.exe')) {
        $env:PATH = (Join-Path $candidate 'usr/bin')+';'+(Join-Path $candidate 'mingw64/bin')+';'+$env:PATH
        break
    }
}
$options = @('-DUSE_STANDALONE=ON','-DBUILD_STORMLIB=OFF','-DBUILD_SM64=OFF',
    '-DBUILD_MK64=OFF','-DBUILD_SF64=OFF','-DBUILD_PM64=OFF','-DBUILD_FZERO=OFF',
    '-DBUILD_MARIO_ARTIST=OFF','-DBUILD_NAUDIO=ON','-DBUILD_SSB64=ON',
    '-DCMAKE_POLICY_VERSION_MINIMUM=3.5')
& cmake -S (Join-Path $root 'upstream/BattleShip/torch') -B $build -G 'Visual Studio 17 2022' -A x64 @options 2>&1 | Tee-Object -FilePath (Join-Path $logs 'torch-configure.log')
if ($LASTEXITCODE -ne 0) { throw 'Host Torch configure failed' }
& cmake --build $build --config Release --target torch --parallel 4 2>&1 | Tee-Object -FilePath (Join-Path $logs 'torch-build.log')
if ($LASTEXITCODE -ne 0) { throw 'Host Torch build failed' }
& python -B (Join-Path $PSScriptRoot 'prepare_assets.py') --extract *> (Join-Path $logs 'assets-extract.log')
if ($LASTEXITCODE -ne 0) { throw 'Asset generation failed' }
Get-Content -LiteralPath (Join-Path $logs 'assets-extract.log') -Tail 4
