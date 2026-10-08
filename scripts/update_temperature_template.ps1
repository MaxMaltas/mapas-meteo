[CmdletBinding()]
param(
    [ValidateSet("Prepare", "Apply", "All")]
    [string]$Stage = "All",

    [ValidatePattern("^\d{4}-\d{2}-\d{2}$")]
    [string]$Date,

    [string]$ProjectPath,

    [switch]$NoLaunch,

    [switch]$NoPublish
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
if (-not $ProjectPath) {
    $ProjectPath = Join-Path $ProjectRoot "temperature_template\project\Mapa_Temperaturas_Semiautomatico.aep"
}
$ProjectPath = [IO.Path]::GetFullPath($ProjectPath)

$TemplateRoot = Join-Path $ProjectRoot "temperature_template"
$DailyDirectory = Join-Path $TemplateRoot ("assets\daily\{0}" -f $Date)
$TexturePath = Join-Path $DailyDirectory "temperatura_rellenada.png"
$ManifestPath = Join-Path $TemplateRoot ("validation\registration_{0}.json" -f $Date)
$RequestPath = Join-Path $TemplateRoot "project\update_request.json"
$LogPath = Join-Path $TemplateRoot ("validation\phase6_daily_{0}.log" -f $Date)

function Write-TemplateLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $line
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
}

function Assert-File {
    param([string]$Path, [long]$MinimumBytes = 1)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Falta el archivo obligatorio: $Path"
    }
    if ((Get-Item -LiteralPath $Path).Length -lt $MinimumBytes) {
        throw "El archivo esta vacio o incompleto: $Path"
    }
}

function Assert-PngSize {
    param([string]$Path, [int]$Width = 1920, [int]$Height = 1080)
    Assert-File -Path $Path -MinimumBytes 1000
    Add-Type -AssemblyName System.Drawing
    $image = $null
    try {
        $image = [Drawing.Image]::FromFile($Path)
        if ($image.Width -ne $Width -or $image.Height -ne $Height) {
            throw "La imagen mide $($image.Width)x$($image.Height); se esperaba ${Width}x${Height}."
        }
    } finally {
        if ($null -ne $image) { $image.Dispose() }
    }
}

function Find-Python {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) { return @($python.Source) }
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) { return @($launcher.Source, "-3") }
    throw "No se encuentra Python (python.exe o py.exe)."
}

function Find-AfterEffects {
    $preferred = "C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\AfterFX.com"
    if (Test-Path -LiteralPath $preferred -PathType Leaf) { return $preferred }
    throw "No se encuentra After Effects 2026."
}

function Write-UpdateRequest {
    $request = [ordered]@{
        date = $Date
        project_path = $ProjectPath.Replace("\", "/")
        texture_path = $TexturePath.Replace("\", "/")
        created_at = (Get-Date).ToString("o")
    }
    $request | ConvertTo-Json | Set-Content -LiteralPath $RequestPath -Encoding UTF8
}

function Invoke-Prepare {
    $peninsulaSource = Join-Path $ProjectRoot "data\raw\$Date\temperaturas_maximas.png"
    $canarySource = Join-Path $ProjectRoot "data\raw\$Date\temperaturas_maximas_canarias.png"
    if (
        -not (Test-Path -LiteralPath $peninsulaSource -PathType Leaf) -or
        -not (Test-Path -LiteralPath $canarySource -PathType Leaf)
    ) {
        $today = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId(
            [DateTime]::UtcNow,
            $MadridTimeZone
        ).ToString("yyyy-MM-dd")
        if ($Date -ne $today) {
            throw "Faltan fuentes historicas de $Date. No se descargaran mapas actuales para una fecha anterior."
        }
        $dailyGenerator = Join-Path $ProjectRoot "scripts\generate_daily.py"
        Assert-File -Path $dailyGenerator
        $downloadPython = @(Find-Python)
        Write-TemplateLog "Descargando las fuentes AEMET frescas de $Date."
        if ($downloadPython.Count -eq 1) {
            & $downloadPython[0] $dailyGenerator --date $Date
        } else {
            & $downloadPython[0] $downloadPython[1] $dailyGenerator --date $Date
        }
        if ($LASTEXITCODE -ne 0) {
            throw "generate_daily.py termino con codigo $LASTEXITCODE."
        }
    }
    Assert-File -Path $peninsulaSource -MinimumBytes 1000
    Assert-File -Path $canarySource -MinimumBytes 1000
    $builder = Join-Path $ProjectRoot "scripts\build_daily_temperature_texture.py"
    Assert-File -Path $builder
    $python = @(Find-Python)
    Write-TemplateLog "Generando textura termica registrada para $Date."
    if ($python.Count -eq 1) {
        & $python[0] $builder --date $Date
    } else {
        & $python[0] $python[1] $builder --date $Date
    }
    if ($LASTEXITCODE -ne 0) {
        throw "build_daily_temperature_texture.py termino con codigo $LASTEXITCODE."
    }
    Assert-PngSize -Path $TexturePath
    Assert-File -Path $ManifestPath -MinimumBytes 100
    $manifest = Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
    if ($manifest.coverage.coverage_percent -lt 99.0) {
        throw "Cobertura insuficiente: $($manifest.coverage.coverage_percent) %."
    }
    if ($manifest.palette.invented_colours -ne 0) {
        throw "La textura contiene colores no autorizados."
    }
    Write-UpdateRequest
    Write-TemplateLog "Textura validada y solicitud de reemplazo preparada."
}

function Invoke-Apply {
    Assert-File -Path $ProjectPath -MinimumBytes 1000
    Assert-PngSize -Path $TexturePath
    Write-UpdateRequest
    if ($NoLaunch) {
        Write-TemplateLog "NoLaunch activo: no se abre After Effects."
        return
    }
    $wrapper = Join-Path $TemplateRoot "project\open_and_update_temperature_template.jsx"
    Assert-File -Path $wrapper
    $runningAfterEffects = Get-Process AfterFX -ErrorAction SilentlyContinue
    if ($runningAfterEffects) {
        throw "After Effects ya esta abierto. Guardalo y cierralo antes de ejecutar la actualizacion automatica."
    }
    $afterEffects = Find-AfterEffects
    $applyLog = Join-Path $TemplateRoot ("validation\phase6_after_effects_update_{0}.log" -f $Date)
    $startedAt = Get-Date
    Write-TemplateLog "Ejecutando el reemplazo en una instancia independiente de After Effects."
    & $afterEffects -m -r $wrapper
    Assert-File -Path $applyLog -MinimumBytes 20
    if ((Get-Item -LiteralPath $applyLog).LastWriteTime -lt $startedAt.AddSeconds(-2)) {
        throw "After Effects no genero una confirmacion nueva para $Date."
    }
    $confirmation = Get-Content -Raw -LiteralPath $applyLog
    if ($confirmation -notmatch "^OK" -or $confirmation -notmatch [regex]::Escape($Date)) {
        throw "La confirmacion de After Effects no es valida."
    }
    Write-TemplateLog "After Effects sustituyo el metraje y guardo el proyecto correctamente."
}

function Invoke-Publish {
    if ($NoLaunch -or $NoPublish) {
        if ($NoPublish) { Write-TemplateLog "NoPublish activo: no se renderiza ni publica el PNG final." }
        return
    }
    $publisher = Join-Path $ProjectRoot "scripts\publish_temperature_template.ps1"
    Assert-File -Path $publisher
    Write-TemplateLog "Renderizando y publicando el mapa final fechado."
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $publisher -Date $Date -ProjectPath $ProjectPath
    if ($LASTEXITCODE -ne 0) {
        throw "publish_temperature_template.ps1 termino con codigo $LASTEXITCODE."
    }
}

try {
    Write-TemplateLog "Inicio. Fase=$Stage; Fecha=$Date; Proyecto=$ProjectPath"
    if ($Stage -eq "Prepare" -or $Stage -eq "All") { Invoke-Prepare }
    if ($Stage -eq "Apply" -or $Stage -eq "All") {
        Invoke-Apply
        Invoke-Publish
    }
    Write-TemplateLog "Flujo de plantilla termica completado."
    exit 0
} catch {
    Write-TemplateLog ("ERROR: {0}" -f $_.Exception.Message)
    Write-Error $_
    exit 1
}
