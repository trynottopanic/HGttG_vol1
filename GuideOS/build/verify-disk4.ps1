$ErrorActionPreference = 'Stop'
$expected = '1F4166A488C96494075D412805F8FB6A47078F96CE80D144CD3D7DBD1FC56256'
$length = 2215641088L
$resultPath = "$PSScriptRoot\verify-disk4-result.txt"

$disk = Get-Disk -Number 4
if ($disk.SerialNumber.Trim() -ne '00000000TS38' -or
    $disk.Size -ne 62239277056 -or $disk.IsBoot -or $disk.IsSystem) {
    throw 'Disk 4 identity or safety state changed.'
}

$buffer = New-Object byte[] 4MB
$stream = $null
$sha = [Security.Cryptography.SHA256]::Create()
try {
    $stream = [IO.FileStream]::new(
        '\\.\PhysicalDrive4', [IO.FileMode]::Open, [IO.FileAccess]::Read,
        [IO.FileShare]::ReadWrite, 4MB, [IO.FileOptions]::SequentialScan)
    $remaining = $length
    while ($remaining -gt 0) {
        if ($remaining -gt $buffer.Length) { $wanted = $buffer.Length }
        else { $wanted = [int]$remaining }
        $read = $stream.Read($buffer, 0, $wanted)
        if ($read -le 0) { throw 'Unexpected end of card during verification.' }
        [void]$sha.TransformBlock($buffer, 0, $read, $buffer, 0)
        $remaining -= $read
    }
    [void]$sha.TransformFinalBlock((New-Object byte[] 0), 0, 0)
    $actual = ([BitConverter]::ToString($sha.Hash)).Replace('-', '')
    "CARD_SHA256=$actual`r`nMATCH=$($actual -eq $expected)" |
        Set-Content -LiteralPath $resultPath -Encoding ASCII
    if ($actual -ne $expected) { exit 2 }
}
finally {
    if ($stream) { $stream.Dispose() }
    $sha.Dispose()
}
