[CmdletBinding()]
param(
    [ValidatePattern("^\d{4}-\d{2}-\d{2}$")]
    [string]$Date,

    [string]$ProjectPath
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
$TexturePath = Join-Path $TemplateRoot ("assets\daily\{0}\temperatura_rellenada.png" -f $Date)
$RegistrationPath = Join-Path $TemplateRoot ("validation\registration_{0}.json" -f $Date)
$ReliefPath = Join-Path $TemplateRoot "assets\static\relieve_dem.png"
$PeninsulaSource = Join-Path $ProjectRoot ("data\raw\{0}\temperaturas_maximas.png" -f $Date)
$CanarySource = Join-Path $ProjectRoot ("data\raw\{0}\temperaturas_maximas_canarias.png" -f $Date)
$OutputDirectory = Join-Path $ProjectRoot ("data\generated\{0}" -f $Date)
$FinalPath = Join-Path $OutputDirectory "temperaturas_final.png"
$RunId = Get-Date -Format "yyyyMMdd-HHmmss"
$StagingDirectory = Join-Path $TemplateRoot ("validation\render_staging\{0}\{1}" -f $Date, $RunId)
$RequestedOutput = Join-Path $StagingDirectory ("temperaturas_final_{0}.png" -f $RunId)
$OutputPrefix = [IO.Path]::GetFileNameWithoutExtension($RequestedOutput)
$RequestPath = Join-Path $TemplateRoot "project\render_request.json"
$RenderLog = Join-Path $StagingDirectory "after_effects_render.log"
$PublishLog = Join-Path $TemplateRoot ("validation\phase7_publish_{0}.log" -f $Date)

function Write-PublishLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $line
    Add-Content -LiteralPath $PublishLog -Value $line -Encoding UTF8
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

function Get-PngDimensions {
    param([string]$Path)
    Add-Type -AssemblyName System.Drawing
    $image = $null
    try {
        $image = [Drawing.Image]::FromFile($Path)
        return [PSCustomObject]@{ Width = $image.Width; Height = $image.Height }
    } finally {
        if ($null -ne $image) { $image.Dispose() }
    }
}

try {
    Write-PublishLog "Inicio de render y publicacion. Fecha=$Date"
    Assert-File -Path $ProjectPath -MinimumBytes 1000
    Assert-File -Path $TexturePath -MinimumBytes 1000
    Assert-File -Path $RegistrationPath -MinimumBytes 100
    Assert-File -Path $ReliefPath -MinimumBytes 1000
    Assert-File -Path $PeninsulaSource -MinimumBytes 1000
    Assert-File -Path $CanarySource -MinimumBytes 1000

    $registration = Get-Content -Raw -LiteralPath $RegistrationPath | ConvertFrom-Json
    if ($registration.date -ne $Date) { throw "El registro termico no corresponde a $Date." }
    if ($registration.coverage.coverage_percent -lt 99.0) { throw "Cobertura termica insuficiente." }
    if ($registration.palette.invented_colours -ne 0) { throw "La textura contiene colores inventados." }

    if (Get-Process AfterFX -ErrorAction SilentlyContinue) {
        throw "After Effects ya esta abierto. Guardalo y cierralo antes de publicar."
    }
    $afterEffects = "C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\AfterFX.com"
    Assert-File -Path $afterEffects -MinimumBytes 1000
    $renderScript = Join-Path $TemplateRoot "project\render_temperature_template.jsx"
    Assert-File -Path $renderScript

    New-Item -ItemType Directory -Force -Path $StagingDirectory | Out-Null
    $request = [ordered]@{
        date = $Date
        project_path = $ProjectPath.Replace("\", "/")
        composition = "TEMP_MAPA_MASTER"
        output_path = $RequestedOutput.Replace("\", "/")
        output_prefix = $OutputPrefix
        log_path = $RenderLog.Replace("\", "/")
    }
    $request | ConvertTo-Json | Set-Content -LiteralPath $RequestPath -Encoding UTF8

    Write-PublishLog "Renderizando el primer fotograma de TEMP_MAPA_MASTER."
    & $afterEffects -m -r $renderScript
    Assert-File -Path $RenderLog -MinimumBytes 20
    $renderConfirmation = Get-Content -Raw -LiteralPath $RenderLog
    if ($renderConfirmation -notmatch "^OK") {
        throw "After Effects no confirmo el render: $renderConfirmation"
    }
    $renderedImage = Get-ChildItem -LiteralPath $StagingDirectory -File |
        Where-Object { $_.Extension -match "^\.(png|tif|tiff)$" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $renderedImage) { throw "No se encontro la imagen renderizada." }
    if ($renderedImage.Extension -notmatch "^\.png$") {
        Add-Type -AssemblyName System.Drawing
        $convertedPath = Join-Path $StagingDirectory ("{0}_converted.png" -f $OutputPrefix)
        $sourceImage = $null
        try {
            $sourceImage = [Drawing.Image]::FromFile($renderedImage.FullName)
            $sourceImage.Save($convertedPath, [Drawing.Imaging.ImageFormat]::Png)
        } finally {
            if ($null -ne $sourceImage) { $sourceImage.Dispose() }
        }
        $renderedPng = Get-Item -LiteralPath $convertedPath
    } else {
        $renderedPng = $renderedImage
    }
    $dimensions = Get-PngDimensions -Path $renderedPng.FullName
    if ($dimensions.Width -ne 1920 -or $dimensions.Height -ne 1080) {
        throw "El render mide $($dimensions.Width)x$($dimensions.Height); se esperaba 1920x1080."
    }
    if ($renderedPng.Length -lt 50000) { throw "El render parece vacio o incompleto." }

    New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
    Copy-Item -LiteralPath $PeninsulaSource -Destination (Join-Path $OutputDirectory "temperaturas_maximas.png") -Force
    Copy-Item -LiteralPath $CanarySource -Destination (Join-Path $OutputDirectory "temperaturas_maximas_canarias.png") -Force
    Copy-Item -LiteralPath $TexturePath -Destination (Join-Path $OutputDirectory "temperatura_rellenada.png") -Force
    $temporaryFinal = Join-Path $OutputDirectory "temperaturas_final.validated.tmp.png"
    Copy-Item -LiteralPath $renderedPng.FullName -Destination $temporaryFinal -Force
    Move-Item -LiteralPath $temporaryFinal -Destination $FinalPath -Force

    $manifest = [ordered]@{
        date = $Date
        status = "rendered_and_published"
        composition = "TEMP_MAPA_MASTER"
        dimensions = @(1920, 1080)
        project = $ProjectPath
        project_sha256 = (Get-FileHash -LiteralPath $ProjectPath -Algorithm SHA256).Hash
        texture_sha256 = (Get-FileHash -LiteralPath $TexturePath -Algorithm SHA256).Hash
        final_sha256 = (Get-FileHash -LiteralPath $FinalPath -Algorithm SHA256).Hash
        coverage_percent = $registration.coverage.coverage_percent
        invented_colours = $registration.palette.invented_colours
        rendered_at = (Get-Date).ToString("o")
        staging_render = $renderedPng.FullName
    }
    $manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $OutputDirectory "temperature_template_manifest.json") -Encoding UTF8
    Remove-Item -LiteralPath $RequestPath -Force -ErrorAction SilentlyContinue
    Write-PublishLog "Publicado correctamente: $FinalPath"
    Write-Output $FinalPath
    exit 0
} catch {
    Write-PublishLog ("ERROR: {0}" -f $_.Exception.Message)
    Write-Error $_
    exit 1
}
