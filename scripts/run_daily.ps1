[CmdletBinding()]
param(
    [ValidateSet("Prepare", "Apply", "All")]
    [string]$Stage = "All",

    [ValidatePattern("^\d{4}-\d{2}-\d{2}$")]
    [string]$Date,

    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$MadridTimeZone = "Romance Standard Time"
if (-not $Date) {
    $Date = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId(
        [DateTime]::UtcNow,
        $MadridTimeZone
    ).ToString("yyyy-MM-dd")
}

try {
    [void][DateTime]::ParseExact(
        $Date,
        "yyyy-MM-dd",
        [Globalization.CultureInfo]::InvariantCulture
    )
} catch {
    throw "La fecha '$Date' no es una fecha ISO valida."
}

$LogDirectory = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
$LogPath = Join-Path $LogDirectory ("daily-{0}.log" -f $Date)

function Write-DailyLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $line
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
}

function Assert-File {
    param(
        [string]$Path,
        [long]$MinimumBytes = 1
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Falta el archivo obligatorio: $Path"
    }
    $item = Get-Item -LiteralPath $Path
    if ($item.Length -lt $MinimumBytes) {
        throw "El archivo esta vacio o incompleto: $Path"
    }
}

function Assert-PngSize {
    param(
        [string]$Path,
        [int]$Width = 1920,
        [int]$Height = 1080
    )
    Assert-File -Path $Path -MinimumBytes 1000
    Add-Type -AssemblyName System.Drawing
    $image = $null
    try {
        $image = [Drawing.Image]::FromFile($Path)
        if ($image.Width -ne $Width -or $image.Height -ne $Height) {
            throw "La imagen '$Path' mide $($image.Width)x$($image.Height); se esperaba ${Width}x${Height}."
        }
    } finally {
        if ($null -ne $image) { $image.Dispose() }
    }
}

function Assert-DailyData {
    $datedDirectory = Join-Path $ProjectRoot ("data\generated\{0}" -f $Date)
    $jsonPath = Join-Path $datedDirectory "meteo.json"
    Assert-File -Path $jsonPath -MinimumBytes 100
    Assert-File -Path (Join-Path $datedDirectory "temperaturas_maximas.png") -MinimumBytes 1000
    Assert-File -Path (Join-Path $datedDirectory "temperaturas_maximas_canarias.png") -MinimumBytes 1000
    Assert-PngSize -Path (Join-Path $datedDirectory "alertas.png")

    $dailyData = Get-Content -LiteralPath $jsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $dailyData.alerts -or $dailyData.alerts.date -ne $Date) {
        throw "El JSON diario no corresponde a $Date."
    }

    $latestJsonPath = Join-Path $ProjectRoot "data\generated\latest\meteo.json"
    Assert-File -Path $latestJsonPath -MinimumBytes 100
    $latestData = Get-Content -LiteralPath $latestJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $latestData.alerts -or $latestData.alerts.date -ne $Date) {
        throw "data/generated/latest/meteo.json no corresponde a $Date."
    }
}

function Invoke-DataPreparation {
    $generator = Join-Path $ProjectRoot "scripts\generate_daily.py"
    Assert-File -Path $generator

    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        Write-DailyLog "Descargando y procesando los datos AEMET de $Date."
        & $python.Source $generator --date $Date
    } else {
        $pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
        if (-not $pyLauncher) {
            throw "No se encuentra Python (python.exe o py.exe) en PATH."
        }
        Write-DailyLog "Descargando y procesando los datos AEMET de $Date."
        & $pyLauncher.Source -3 $generator --date $Date
    }
    if ($LASTEXITCODE -ne 0) {
        throw "generate_daily.py termino con el codigo $LASTEXITCODE."
    }
    Assert-DailyData
    Write-DailyLog "Datos tecnicos y descargas preparados correctamente."
}

function Find-AfterEffects {
    $preferred = "C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\AfterFX.exe"
    if (Test-Path -LiteralPath $preferred -PathType Leaf) {
        return $preferred
    }

    $adobeRoot = "C:\Program Files\Adobe"
    if (Test-Path -LiteralPath $adobeRoot -PathType Container) {
        $candidate = Get-ChildItem -LiteralPath $adobeRoot -Directory -Filter "Adobe After Effects *" |
            Sort-Object Name -Descending |
            ForEach-Object { Join-Path $_.FullName "Support Files\AfterFX.exe" } |
            Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
            Select-Object -First 1
        if ($candidate) { return $candidate }
    }
    throw "No se encuentra AfterFX.exe. Instala After Effects o actualiza Find-AfterEffects en este script."
}

function Invoke-AfterEffectsApply {
    Assert-DailyData
    $datedDirectory = Join-Path $ProjectRoot ("data\generated\{0}" -f $Date)
    Assert-PngSize -Path (Join-Path $datedDirectory "temperaturas_final.png") -Width 1672 -Height 941
    Assert-PngSize -Path (Join-Path $datedDirectory "alertas_final.png") -Width 1672 -Height 941

    $wrapper = Join-Path $ProjectRoot "tools\open_and_apply_daily_data.jsx"
    Assert-File -Path $wrapper
    Write-DailyLog "Las dos imagenes finales de $Date han superado las comprobaciones."

    if ($NoLaunch) {
        Write-DailyLog "NoLaunch activo: no se abre After Effects."
        return
    }

    $afterEffects = Find-AfterEffects
    Write-DailyLog "Abriendo METEO FINAL.aep y ejecutando apply_daily_data.jsx en After Effects."
    Start-Process -FilePath $afterEffects -ArgumentList @("-r", ('"{0}"' -f $wrapper))
}

try {
    Write-DailyLog "Inicio del flujo diario. Fase: $Stage. Fecha: $Date."
    if ($Stage -eq "Prepare" -or $Stage -eq "All") {
        Invoke-DataPreparation
    }
    if ($Stage -eq "Apply" -or $Stage -eq "All") {
        Invoke-AfterEffectsApply
    }
    Write-DailyLog "Flujo diario completado."
    exit 0
} catch {
    Write-DailyLog ("ERROR: {0}" -f $_.Exception.Message)
    Write-Error $_
    exit 1
}
