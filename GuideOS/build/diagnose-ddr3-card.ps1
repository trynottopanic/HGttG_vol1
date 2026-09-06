$ErrorActionPreference = 'Stop'
$imagePath = Join-Path $PSScriptRoot 'GuideOS-RG35XXH-ddr3.img'
$resultPath = Join-Path $PSScriptRoot 'diagnose-ddr3-card-result.txt'
$expectedModel = 'TS-RDF5 SD  Transcend'
$expectedSerial = '00000000TS38'
$expectedSize = 62239277056
$chunkSize = 1MB

$disk = Get-Disk -Number 4
if ($disk.FriendlyName -ne $expectedModel -or
    $disk.SerialNumber.Trim() -ne $expectedSerial -or
    $disk.Size -ne $expectedSize -or
    $disk.IsBoot -or $disk.IsSystem) {
    throw 'Disk 4 identity or safety state changed.'
}

Add-Type @'
using System;
using System.IO;

public static class GuideCardComparer {
    public static string Compare(string imagePath, string cardPath, int chunkSize) {
        byte[] a = new byte[chunkSize];
        byte[] b = new byte[chunkSize];
        long differentBytes = 0;
        long firstDifference = -1;
        long lastDifference = -1;
        long differentChunks = 0;
        using (var image = new FileStream(imagePath, FileMode.Open, FileAccess.Read,
                   FileShare.Read, chunkSize, FileOptions.SequentialScan))
        using (var card = new FileStream(cardPath, FileMode.Open, FileAccess.Read,
                   FileShare.ReadWrite, chunkSize, FileOptions.SequentialScan)) {
            long offset = 0;
            while (offset < image.Length) {
                int wanted = (int)Math.Min(chunkSize, image.Length - offset);
                ReadExactly(image, a, wanted);
                ReadExactly(card, b, wanted);
                bool chunkDifferent = false;
                for (int i = 0; i < wanted; i++) {
                    if (a[i] == b[i]) continue;
                    long position = offset + i;
                    if (firstDifference < 0) firstDifference = position;
                    lastDifference = position;
                    differentBytes++;
                    chunkDifferent = true;
                }
                if (chunkDifferent) differentChunks++;
                offset += wanted;
            }
            return "IMAGE_BYTES=" + image.Length + Environment.NewLine +
                   "DIFFERENT_CHUNKS_1M=" + differentChunks + Environment.NewLine +
                   "DIFFERENT_BYTES=" + differentBytes + Environment.NewLine +
                   "FIRST_DIFFERENCE=" + firstDifference + Environment.NewLine +
                   "LAST_DIFFERENCE=" + lastDifference + Environment.NewLine;
        }
    }

    private static void ReadExactly(Stream stream, byte[] buffer, int count) {
        int offset = 0;
        while (offset < count) {
            int read = stream.Read(buffer, offset, count - offset);
            if (read <= 0) throw new EndOfStreamException("Unexpected short read.");
            offset += read;
        }
    }
}
'@

$comparison = [GuideCardComparer]::Compare($imagePath, '\\.\PhysicalDrive4', $chunkSize)
$comparison | Set-Content -LiteralPath $resultPath -Encoding ascii
