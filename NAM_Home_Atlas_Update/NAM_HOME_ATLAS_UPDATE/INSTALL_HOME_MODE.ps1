$ErrorActionPreference = 'Stop'
$patchRoot = $PSScriptRoot
$repoRoot = Split-Path -Parent $patchRoot
$frontend = Join-Path $repoRoot 'nam-v2\frontend'
$indexPath = Join-Path $frontend 'index.html'
$appPath = Join-Path $frontend 'app.js'
$stylesPath = Join-Path $frontend 'styles.css'

Write-Host ''
Write-Host 'NAM — Home / Atlas integration' -ForegroundColor Cyan
Write-Host '--------------------------------'

if (!(Test-Path $indexPath) -or !(Test-Path $appPath) -or !(Test-Path $stylesPath)) {
  Write-Host 'Could not find nam-v2\frontend\index.html, app.js and styles.css.' -ForegroundColor Red
  Write-Host 'Extract the NAM_HOME_ATLAS_UPDATE folder directly into your GitHub repository root.' -ForegroundColor Yellow
  Write-Host 'Expected repository root to contain the nam-v2 folder.'
  Read-Host 'Press Enter to close'
  exit 1
}

$sourceJs = Join-Path $patchRoot 'nam-v2\frontend\nam-home-mode.js'
$sourceCss = Join-Path $patchRoot 'nam-v2\frontend\nam-home-mode.css'
if (!(Test-Path $sourceJs) -or !(Test-Path $sourceCss)) {
  Write-Host 'The home-mode files are missing from the update package.' -ForegroundColor Red
  Read-Host 'Press Enter to close'
  exit 1
}

Copy-Item $sourceJs (Join-Path $frontend 'nam-home-mode.js') -Force
Copy-Item $sourceCss (Join-Path $frontend 'nam-home-mode.css') -Force

$html = Get-Content $indexPath -Raw
$original = $html

if ($html -notmatch 'nam-home-mode\.css') {
  $pattern = '(?m)(\s*<link\s+rel="stylesheet"\s+href="\./styles\.css"\s*/?>)'
  if ($html -notmatch $pattern) { throw 'Could not find the existing styles.css link in index.html.' }
  $html = [regex]::Replace($html, $pattern, ('$1' + "`r`n  <link rel=`"stylesheet`" href=`"./nam-home-mode.css`" />"), 1)
}

if ($html -notmatch 'nam-home-mode\.js') {
  $pattern = '(?m)(\s*<script\s+src="\./app\.js"\s+defer\s*></script>)'
  if ($html -notmatch $pattern) { throw 'Could not find the existing app.js script tag in index.html.' }
  $html = [regex]::Replace($html, $pattern, ('  <script src="./nam-home-mode.js"></script>' + "`r`n" + '$1'), 1)
}

$html = $html.Replace('<title>Marswalk — planetary atlas</title>', '<title>NAM — Navigation Assistant for Mars</title>')
$html = $html.Replace('content="#101311"', 'content="#101114"')

if ($html -ne $original) {
  $backupPath = Join-Path $frontend 'index.html.before-nam-home-mode.bak'
  if (!(Test-Path $backupPath)) { Copy-Item $indexPath $backupPath }
  Set-Content -Path $indexPath -Value $html -Encoding UTF8
  Write-Host 'Updated index.html (backup created).' -ForegroundColor Green
} else {
  Write-Host 'index.html already has the home-mode references; no duplicate tags added.' -ForegroundColor Yellow
}

Write-Host ''
Write-Host 'Done. Your existing app.js and styles.css were not modified.' -ForegroundColor Green
Write-Host 'Open nam-v2\frontend in VS Code and run it the way you normally do.'
Write-Host 'The first screen is Home Mode. Click Enter MARSWALK to fly into the atlas.'
Write-Host ''
Read-Host 'Press Enter to close'
