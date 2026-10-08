param(
    [string]$FontPath = 'C:\Windows\Fonts\OCRAEXT.TTF',
    [string]$OutputPath = (Join-Path $PSScriptRoot 'assets\caption-dont-panic-v3.r8')
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

if (-not (Test-Path -LiteralPath $FontPath -PathType Leaf)) {
    throw "Required OCR A Extended font was not found at: $FontPath"
}

$width = 132
$height = 18
$text = "Don't Panic."
$bitmap = [System.Drawing.Bitmap]::new($width, $height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$fonts = [System.Drawing.Text.PrivateFontCollection]::new()
$format = [System.Drawing.StringFormat]::GenericTypographic.Clone()

try {
    $fonts.AddFontFile($FontPath)
    $font = [System.Drawing.Font]::new(
        $fonts.Families[0],
        14.0,
        [System.Drawing.FontStyle]::Regular,
        [System.Drawing.GraphicsUnit]::Pixel
    )
    $graphics.Clear([System.Drawing.Color]::Transparent)
    $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::SingleBitPerPixelGridFit
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::None
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::Half
    $format.FormatFlags = $format.FormatFlags -bor [System.Drawing.StringFormatFlags]::NoWrap
    $measured = $graphics.MeasureString($text, $font, 1000, $format)
    $x = [Math]::Floor(($width - $measured.Width) / 2.0)
    $y = [Math]::Floor(($height - $measured.Height) / 2.0) - 1
    $brush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::White)
    try {
        $graphics.DrawString($text, $font, $brush, [single]$x, [single]$y, $format)
    }
    finally {
        $brush.Dispose()
        $font.Dispose()
    }

    $parent = Split-Path -Parent $OutputPath
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $bytes = [byte[]]::new($width * $height)
    for ($row = 0; $row -lt $height; $row++) {
        for ($column = 0; $column -lt $width; $column++) {
            $bytes[$row * $width + $column] = $bitmap.GetPixel($column, $row).A
        }
    }
    [System.IO.File]::WriteAllBytes($OutputPath, $bytes)
    Write-Output "GUIDE_CAPTION_FONT_ASSET_READY"
    Write-Output "font=$($fonts.Families[0].Name)"
    Write-Output "text=$text"
    Write-Output "size=${width}x${height}"
    Write-Output "output=$OutputPath"
}
finally {
    $format.Dispose()
    $fonts.Dispose()
    $graphics.Dispose()
    $bitmap.Dispose()
}
