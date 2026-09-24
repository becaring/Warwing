param([switch]$VerifyOnly)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$entries = Get-Content -LiteralPath (Join-Path $root 'dependencies.lock.json') -Raw | ConvertFrom-Json
foreach ($entry in $entries) {
    $path = [IO.Path]::GetFullPath((Join-Path $root $entry.path))
    if (!$path.StartsWith($root+[IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Dependency path escapes Smash360' }
    $safe = @('-c', ('safe.directory='+$path.Replace('\','/')))
    if (!(Test-Path -LiteralPath $path)) {
        if ($VerifyOnly) { throw "Missing dependency: $($entry.path)" }
        & git @safe clone $entry.url $path
        if ($LASTEXITCODE -ne 0) { throw 'Dependency clone failed' }
    }
    $dirty = & git @safe -C $path status --porcelain
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect dependency' }
    if ($dirty) { throw "Dependency has local changes: $($entry.path)" }
    $revision = & git @safe -C $path rev-parse HEAD
    if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve dependency revision' }
    if ($revision -ne $entry.revision) {
        if ($VerifyOnly) { throw "Dependency revision mismatch: $($entry.path)" }
        & git @safe -C $path cat-file -e ($entry.revision+'^{commit}')
        if ($LASTEXITCODE -ne 0) {
            & git @safe -C $path fetch origin $entry.revision
            if ($LASTEXITCODE -ne 0) { throw 'Pinned dependency fetch failed' }
        }
        & git @safe -C $path checkout --detach $entry.revision
        if ($LASTEXITCODE -ne 0) { throw 'Pinned dependency checkout failed' }
    }
    Write-Output "$($entry.path): clean at $($entry.revision)"
}
