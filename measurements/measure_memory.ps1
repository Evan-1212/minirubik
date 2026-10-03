$Ripes = "C:\Tools\Ripes\Ripes.exe"
$WorkDir = "C:\Tools\Ripes\hw1_measurements"
$Runs = 5

function Measure-RipesPeak {
    param (
        [string]$Source,
        [string]$Report
    )

    $p = Start-Process `
        -FilePath $Ripes `
        -WorkingDirectory $WorkDir `
        -ArgumentList "--mode cli --src $Source -t asm --proc RV32_ISS --iret --output $Report" `
        -PassThru

    $peak = 0L

    while (-not $p.HasExited) {
        try {
            $p.Refresh()

            if ($p.PeakWorkingSet64 -gt $peak) {
                $peak = $p.PeakWorkingSet64
            }
        }
        catch {
        }

        Start-Sleep -Milliseconds 10
    }

    if ($p.ExitCode -ne 0) {
        throw "$Source exited with code $($p.ExitCode)"
    }

    return $peak
}

function Get-Median {
    param (
        [long[]]$Values
    )

    $sorted = $Values | Sort-Object
    $count = $sorted.Count

    if ($count % 2 -eq 1) {
        return [double]$sorted[[int][math]::Floor($count / 2)]
    }
    else {
        $a = $sorted[$count / 2 - 1]
        $b = $sorted[$count / 2]
        return ([double]$a + [double]$b) / 2
    }
}

$smallResults = @()
$largeResults = @()
$rows = @()

Write-Host ""
Write-Host "Ripes memory measurement"
Write-Host "Processor: RV32_ISS"
Write-Host "Runs per case: $Runs"
Write-Host ""

for ($i = 1; $i -le $Runs; $i++) {

    Write-Host "Round $i / $Runs"

    $small = Measure-RipesPeak `
        -Source "mem_small.s" `
        -Report "small_report_$i.txt"

    $smallResults += $small

    Write-Host ("  Small: {0:N0} bytes ({1:N2} MiB)" -f `
        $small, ($small / 1MB))

    Start-Sleep -Seconds 1

    $large = Measure-RipesPeak `
        -Source "mem_large.s" `
        -Report "large_report_$i.txt"

    $largeResults += $large

    Write-Host ("  Large: {0:N0} bytes ({1:N2} MiB)" -f `
        $large, ($large / 1MB))

    $rows += [PSCustomObject]@{
        Run             = $i
        SmallPeakBytes  = $small
        SmallPeakMiB    = [math]::Round($small / 1MB, 2)
        LargePeakBytes  = $large
        LargePeakMiB    = [math]::Round($large / 1MB, 2)
    }

    Start-Sleep -Seconds 1
}

$smallMedian = Get-Median $smallResults
$largeMedian = Get-Median $largeResults

$smallGuestBytes = 65536
$largeGuestBytes = 4194304
$guestDifference = $largeGuestBytes - $smallGuestBytes

$hostDifference = $largeMedian - $smallMedian
$ratio = $hostDifference / $guestDifference

Write-Host ""
Write-Host "================ RESULTS ================"
Write-Host ""

$rows | Format-Table -AutoSize

Write-Host ("Small median peak : {0:N0} bytes ({1:N2} MiB)" -f `
    $smallMedian, ($smallMedian / 1MB))

Write-Host ("Large median peak : {0:N0} bytes ({1:N2} MiB)" -f `
    $largeMedian, ($largeMedian / 1MB))

Write-Host ("Host difference   : {0:N0} bytes" -f $hostDifference)
Write-Host ("Guest difference  : {0:N0} bytes" -f $guestDifference)

Write-Host ("Host bytes / guest byte = {0:N2}" -f $ratio)

Write-Host ""
Write-Host "========================================="

$rows | Export-Csv `
    -Path "$WorkDir\memory_measurements.csv" `
    -NoTypeInformation

@"
Ripes version: v2.2.6-106-g5b8a616
Processor: RV32_ISS
Runs per case: $Runs

Small guest region: $smallGuestBytes bytes
Large guest region: $largeGuestBytes bytes
Guest-byte difference: $guestDifference bytes

Small median peak: $smallMedian bytes
Large median peak: $largeMedian bytes
Host-memory difference: $hostDifference bytes

Host bytes per guest byte: $([math]::Round($ratio, 2))
"@ | Set-Content "$WorkDir\memory_summary.txt"