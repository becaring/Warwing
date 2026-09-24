param([string]$JsonInclude = '', [string]$JsonSource = '', [string]$Label = 'original', [ValidateSet('config','cvar','resource')][string]$Consumer = 'config')
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if ($Label -notmatch '^[a-zA-Z0-9_-]+$') { throw 'Invalid output label' }
$out = Join-Path $root ('scratch/json-consumers/'+$Label+'/'+$Consumer)
$include = Join-Path $out 'include'
New-Item -ItemType Directory -Force (Join-Path $include 'SDL2') | Out-Null
Copy-Item (Join-Path $root 'upstream/dependencies/SDL/include/*.h') (Join-Path $include 'SDL2')
$lus = Join-Path $root 'upstream/BattleShip/libultraship'
$cvars = [IO.File]::ReadAllText((Join-Path $lus 'cmake/cvars.cmake'))
$definitions = [regex]::Matches($cvars, 'set\((CVAR_\w+) "([^"\r\n]+)" CACHE STRING ""\)') | ForEach-Object { '#define '+$_.Groups[1].Value+' "'+$_.Groups[2].Value+'"' }
$cvarHeader = Join-Path $out 'cvars.h'
$definitions | Set-Content -LiteralPath $cvarHeader -Encoding Ascii
if (!$JsonInclude) { $JsonInclude = Join-Path $root 'upstream/dependencies/json/include' }
$paths = @($JsonInclude, $include, (Join-Path $lus 'include'), (Join-Path $lus 'src'),
    (Join-Path $root 'upstream/dependencies/spdlog/include'), (Join-Path $root 'upstream/dependencies/imgui'),
    (Join-Path $root 'upstream/dependencies/tinyxml2'), (Join-Path $root 'upstream/dependencies/thread-pool/include'),
    (Join-Path $root 'upstream/BattleShip/torch/lib/n64graphics'),
    (Join-Path $root 'platform/xbox360/cpp-compat'), (Join-Path $root 'scratch/json-xdk/backend-generated'))
$flags = ($paths | ForEach-Object { '/I"'+$_+'"' }) -join ' '
$sources = @((Join-Path $lus 'src/ship/config/Config.cpp'), (Join-Path $lus 'src/ship/utils/StringHelper.cpp'),
    (Join-Path $PSScriptRoot ($Consumer+'_contract.cpp')))
if ($Consumer -eq 'resource') {
    $sources = @((Join-Path $PSScriptRoot 'resource_contract.cpp'), (Join-Path $PSScriptRoot 'resource_fixture.cpp'), (Join-Path $root 'upstream/dependencies/tinyxml2/tinyxml2.cpp'))
    @('resource/ResourceLoader.cpp','resource/Resource.cpp','resource/ResourceFactoryBinary.cpp',
      'resource/factory/JsonFactory.cpp','resource/factory/ShaderFactory.cpp',
      'resource/type/Json.cpp','resource/type/Shader.cpp',
      'utils/binarytools/BinaryReader.cpp','utils/binarytools/MemoryStream.cpp','utils/binarytools/Stream.cpp') | ForEach-Object { $sources += Join-Path $lus ('src/ship/'+$_) }
}
elseif ($Consumer -eq 'config') { $sources += Join-Path $PSScriptRoot 'unused_services.cpp' }
else {
    $sources += Join-Path $PSScriptRoot 'context_fixture.cpp'
    $sources += Join-Path $lus 'src/ship/config/ConsoleVariable.cpp'
}
if ($JsonSource) { $sources += $JsonSource }
$sourceArgs = ($sources | ForEach-Object { '"'+$_+'"' }) -join ' '
$compileLines = @()
$objects = @()
for ($i = 0; $i -lt $sources.Count; $i++) {
    $object = Join-Path $out ('unit_'+$i+'.obj')
    $objects += '"'+$object+'"'
    $compileLines += 'cl /nologo /c /std:c++20 /utf-8 /EHsc /MT /Gy /O1 /W3 /DDISABLE_SCRIPTING /DSDL_MAIN_HANDLED /D_CRT_SECURE_NO_WARNINGS /FI"'+$cvarHeader+'" '+$flags+' "'+$sources[$i]+'" /Fo"'+$object+'"'
    $compileLines += 'if errorlevel 1 exit /b 1'
}
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$vcvars = Join-Path $vs 'VC/Auxiliary/Build/vcvars64.bat'
$exe = Join-Path $out 'config_contract.exe'
$batch = Join-Path $out 'build.cmd'
@"
@echo off
call "$vcvars" >nul
if errorlevel 1 exit /b 1
$($compileLines -join "`r`n")
link /nologo $($objects -join ' ') /OUT:"$exe" /OPT:REF
exit /b %errorlevel%
"@ | Set-Content -LiteralPath $batch -Encoding Ascii
& $env:ComSpec /d /c $batch *> (Join-Path $out 'build.log')
if ($LASTEXITCODE -ne 0) {
    Get-Content (Join-Path $out 'build.log') -Tail 30
    throw 'Real Config consumer build failed'
}
& $exe (Join-Path $out 'settings.json') *> (Join-Path $out 'result.log')
$result = $LASTEXITCODE
Get-Content (Join-Path $out 'result.log')
if ($result -ne 0) { throw 'Real Config consumer contract failed' }
