$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$out = Join-Path $root 'scratch/imgui-xdk'
& python -B (Join-Path $root 'tools/prepare_imgui_xdk.py') --compile
if ($LASTEXITCODE) { throw 'Native ImGui compilation failed' }
$reference = Join-Path $out 'reference'
New-Item -ItemType Directory -Force $reference | Out-Null
Get-ChildItem (Join-Path $root 'upstream/dependencies/imgui') -File | Where-Object { $_.Extension -in '.cpp','.h' } | Copy-Item -Destination $reference
$config = [IO.File]::ReadAllText((Join-Path $reference 'imconfig.h')).Replace('//#define IMGUI_DEFINE_MATH_OPERATORS','#define IMGUI_DEFINE_MATH_OPERATORS') + "`n#define ImTextureID void*`n"
[IO.File]::WriteAllText((Join-Path $reference 'imconfig.h'), $config)
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$vcvars = Join-Path $vs 'VC/Auxiliary/Build/vcvars64.bat'
foreach ($mode in @('reference','source')) {
    $inputDir = Join-Path $out $mode
    $objects = Join-Path $out ('host-'+$mode)
    New-Item -ItemType Directory -Force $objects | Out-Null
    $sources = @('imgui.cpp','imgui_draw.cpp','imgui_tables.cpp','imgui_widgets.cpp','imgui_demo.cpp') | ForEach-Object { '"'+(Join-Path $inputDir $_)+'"' }
    $fixture = Join-Path $PSScriptRoot 'contract.cpp'
    $batch = Join-Path $objects 'build.cmd'
    @"
@echo off
call "$vcvars" >nul
if errorlevel 1 exit /b 1
cl /nologo /std:c++20 /EHsc /MT /W3 /DIMGUI_DISABLE_WIN32_FUNCTIONS /DIMGUI_DISABLE_DEFAULT_SHELL_FUNCTIONS /D_CRT_SECURE_NO_WARNINGS /I"$inputDir" /I"$root/platform/xbox360/imgui" $($sources -join ' ') "$fixture" /Fo"$objects\\" /Fe"$objects/contract.exe"
exit /b %errorlevel%
"@ | Set-Content $batch -Encoding ascii
    & $env:ComSpec /d /c $batch *> (Join-Path $objects 'build.log')
    if ($LASTEXITCODE) { Get-Content (Join-Path $objects 'build.log') -Tail 18; throw 'ImGui host fixture compile failed' }
    & (Join-Path $objects 'contract.exe') (Join-Path $objects 'result.txt')
    if ($LASTEXITCODE) { throw 'ImGui host fixture failed' }
}
$expected = [IO.File]::ReadAllText((Join-Path $out 'host-reference/result.txt'))
$actual = [IO.File]::ReadAllText((Join-Path $out 'host-source/result.txt'))
if ($expected -ne $actual) { throw 'Original/adapted real ImGui draw-data mismatch' }
Write-Output ('PASS original/adapted real ImGui font atlas, defaults, enum ABI and frame draw data: '+$actual.Trim())
