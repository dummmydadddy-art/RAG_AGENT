param(
    [int]$Port = 8000
)

Set-Location $PSScriptRoot

$phpPath = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages\PHP.PHP.8.3_Microsoft.Winget.Source_8wekyb3d8bbwe\php.exe'
if (-not (Test-Path $phpPath)) {
    throw 'PHP was not found. Install PHP 8.3 or add php.exe to PATH.'
}

& $phpPath -S "0.0.0.0:$Port"