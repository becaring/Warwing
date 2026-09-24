# Compile-only reconstruction evidence. Does not build or run an application.
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$xdk = if ($env:XEDK) { $env:XEDK } else { 'C:\Program Files (x86)\Microsoft Xbox 360 SDK' }
$compiler = Join-Path $xdk 'bin\win32\cl.exe'
$audit = Join-Path $root 'scratch\audit'
$logs = Join-Path $root 'scratch\logs'
New-Item -ItemType Directory -Force -Path $audit,$logs | Out-Null
$source = Join-Path $root 'upstream\BattleShip\port\coroutine_win32.cpp'
$original = [IO.File]::ReadAllText($source)
$generated = '#line 1 "upstream/BattleShip/port/coroutine_win32.cpp"' + "`n" + $original.Replace('#include <windows.h>','#include <xtl.h>').Replace('static thread_local PortCoroutine','static __declspec(thread) PortCoroutine')
$output = Join-Path $audit 'coroutine-xdk-tls.cpp'
[IO.File]::WriteAllText($output,$generated)
$flags = @('/nologo','/TP','/D_XBOX','/D_WIN32',('/I'+(Join-Path $xdk 'include\xbox')))
& $compiler @flags /c /MT ('/I'+(Split-Path $source -Parent)) ('/Fo'+(Join-Path $audit 'coroutine-xdk-tls.obj')) $output 2>&1 | Tee-Object -FilePath (Join-Path $logs 'coroutine-xdk-tls-compile.log')
if ($LASTEXITCODE -ne 0) { throw 'Coroutine compiler probe failed' }
$endianHeader = Join-Path $root 'upstream\BattleShip\libultraship\include\ship\utils\binarytools\endianness.h'
& $compiler @flags /EP $endianHeader 2> (Join-Path $logs 'endianness-preprocess-errors.log') | Set-Content (Join-Path $audit 'endianness-xdk.i')
if ($LASTEXITCODE -ne 0) { throw 'Endian preprocessing failed' }
@{
    source = 'upstream/BattleShip/port/coroutine_win32.cpp'
    source_sha256 = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    generated_sha256 = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash
    compiler = $compiler
    compiler_sha256 = (Get-FileHash -LiteralPath $compiler -Algorithm SHA256).Hash
    transformations = @('windows.h include -> xtl.h', 'static thread_local PortCoroutine -> static __declspec(thread) PortCoroutine')
    scope = 'Object compilation only; no link or runtime validation'
} | ConvertTo-Json | Set-Content (Join-Path $audit 'coroutine-provenance.json')
Select-String -Path (Join-Path $audit 'endianness-xdk.i') -Pattern 'Native = '
Write-Output 'Compile-only coroutine probe complete. This is not an application build or boot.'
