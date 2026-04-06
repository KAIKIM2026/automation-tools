$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonScript = Join-Path $projectRoot "src\python\slideshow_backend.py"
$outputDir = Join-Path $projectRoot "dist-python"

$pythonCandidates = @()

if ($env:SLIDESHOW_PYTHON) {
  $pythonCandidates += $env:SLIDESHOW_PYTHON
}

$pythonCandidates += @(
  (Join-Path $env:USERPROFILE "AppData\Local\Programs\Python\Python314\python.exe"),
  "python"
)

$pythonExe = $null
foreach ($candidate in $pythonCandidates) {
  if (-not $candidate) {
    continue
  }

  if ($candidate -eq "python") {
    try {
      & python --version *> $null
      $pythonExe = "python"
      break
    } catch {
      continue
    }
  }

  if (Test-Path -LiteralPath $candidate) {
    $pythonExe = $candidate
    break
  }
}

if (-not $pythonExe) {
  throw "Python executable was not found. Set SLIDESHOW_PYTHON or install Python first."
}

try {
  & $pythonExe -m PyInstaller --version *> $null
} catch {
  throw "PyInstaller is not installed for the selected Python. Run 'pip install pyinstaller' first."
}

if (Test-Path -LiteralPath $outputDir) {
  Remove-Item -LiteralPath $outputDir -Recurse -Force
}

& $pythonExe -m PyInstaller `
  --noconfirm `
  --onefile `
  --name slideshow_backend `
  --distpath $outputDir `
  --workpath (Join-Path $projectRoot "build\pyinstaller") `
  --specpath (Join-Path $projectRoot "build\pyinstaller") `
  $pythonScript

Write-Host ""
Write-Host "Backend build complete:"
Write-Host (Join-Path $outputDir "slideshow_backend.exe")
