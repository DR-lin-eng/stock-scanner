$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$appName = "StockAnalyzerDesktop"
$mainScript = "desktop_gui_launcher.py"
$sourceSampleConfig = "config - 示例.json"
$safeSampleConfig = "config_sample.json"
$tempDir = Join-Path $PSScriptRoot ".build_temp"
$tempSamplePath = Join-Path $tempDir $safeSampleConfig
$excludeModules = @(
    "torch",
    "torchvision",
    "torchaudio",
    "tensorflow",
    "paddle",
    "cv2",
    "scipy",
    "sklearn",
    "matplotlib",
    "nltk",
    "transformers",
    "bitsandbytes",
    "onnxruntime",
    "PyQt5",
    "PyQt6",
    "PySide6",
    "pygame",
    "librosa",
    "soundfile",
    "datasets",
    "fugashi",
    "numba",
    "sympy",
    "sphinx"
)

if (-not (Test-Path $mainScript)) {
    Write-Host "Main script not found: $mainScript" -ForegroundColor Red
    exit 1
}

$pyinstallerCmd = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $pyinstallerCmd) {
    Write-Host "PyInstaller is not installed. Run:" -ForegroundColor Yellow
    Write-Host "  pip install pyinstaller"
    exit 1
}

if (Test-Path $tempDir) {
    Remove-Item -Path $tempDir -Recurse -Force
}
New-Item -Path $tempDir -ItemType Directory | Out-Null

try {
    if (Test-Path $sourceSampleConfig) {
        Copy-Item -Path $sourceSampleConfig -Destination $tempSamplePath -Force
    }
    else {
        "{}" | Set-Content -Path $tempSamplePath -Encoding UTF8
    }

    $args = @(
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name", $appName,
        "--add-data", "$tempSamplePath;.",
        "--hidden-import", "openai",
        "--hidden-import", "anthropic",
        "--hidden-import", "zhipuai",
        "--hidden-import", "numpy._core._exceptions",
        "--collect-submodules", "numpy._core",
        "--collect-data", "akshare",
        $mainScript
    )

    foreach ($module in $excludeModules) {
        $args += @("--exclude-module", $module)
    }

    Write-Host "Starting build..." -ForegroundColor Cyan
    Write-Host "Command: pyinstaller $($args -join ' ')" -ForegroundColor DarkGray

    & pyinstaller @args
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Build failed. Exit code: $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}
finally {
    if (Test-Path $tempDir) {
        Remove-Item -Path $tempDir -Recurse -Force
    }
}

$exePath = Join-Path $PSScriptRoot "dist\$appName\$appName.exe"
Write-Host ""
Write-Host "Build completed." -ForegroundColor Green
Write-Host "EXE path: $exePath"
Write-Host "You can edit settings directly in the GUI Config Center."
