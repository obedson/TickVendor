$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$assetRoot = Join-Path $PSScriptRoot '../public'
$source = [System.Drawing.Image]::FromFile((Join-Path $assetRoot 'tickvendor-icon-source.png'))
try {
    foreach ($size in @(32, 180, 192, 512)) {
        $bitmap = New-Object System.Drawing.Bitmap($size, $size)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        try {
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            # Preserve the supplied artwork and its aspect ratio, including its background.
            $background = ([System.Drawing.Bitmap]$source).GetPixel(0, 0)
            $graphics.Clear($background)
            $scale = ($size * 0.70) / [Math]::Max($source.Width, $source.Height)
            $width = [int]($source.Width * $scale)
            $height = [int]($source.Height * $scale)
            $graphics.DrawImage($source, [int](($size - $width) / 2), [int](($size - $height) / 2), $width, $height)
            $bitmap.Save((Join-Path $assetRoot "tickvendor-icon-v1-$size.png"), [System.Drawing.Imaging.ImageFormat]::Png)
        } finally { $graphics.Dispose(); $bitmap.Dispose() }
    }
} finally { $source.Dispose() }
