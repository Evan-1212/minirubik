$Ripes = "C:\Tools\Ripes\Ripes.exe"
$WorkDir = "C:\Tools\Ripes\hw1_measurements"
$Runs = 5

function Get-Median {
    param ([double[]]$Values)

    $sorted = $Values | Sort-Object
    $count = $sorted.Count

    if ($count % 2 -eq 1) {
        return [double]$sorted[[int][math]::Floor($count / 2)]
    }
    else {
        return ($sorted[$count / 2 - 1] + $sorted[$count / 2]) / 2
    }
}

function Measure-Rate {
    param (
        [string]$Processor,
        [int]$Run
    )

    $reportName = "rate_${Processor}_${Run}.txt"
    $reportPath = Join-Path $WorkDir $reportName

    if (Test-Path $reportPath) {
        Remove-Item $reportPath
    }

    $args = "--mode cli --src measure_rate.s -t asm --proc $Processor --iret --exectime --runinfo --output $reportName"

    $p = Start-Process `
        -FilePath $Ripes `
        -WorkingDirectory $WorkDir `
        -ArgumentList $args `
        -PassThru `
        -Wait

    if ($p.ExitCode -ne 0) {
        throw "Ripes failed for $Processor run $Run with exit code $($p.ExitCode)"
    }

    if (-not (Test-Path $reportPath)) {
        throw "Ripes did not create $reportName"
    }

    $lines = Get-Content $reportPath

    $iretHeader = $lines | Select-String "^===== instructions retired"
    $timeHeader = $lines | Select-String "^===== wall-clock model execution time"

    if (-not $iretHeader -or -not $timeHeader) {
        throw "Could not find measurement fields in $reportName"
    }

    # LineNumber is 1-based, while PowerShell array indices are 0-based.
    # Therefore using LineNumber directly selects the line AFTER the header.
    $iret = [long]$lines[$iretHeader.LineNumber]
    $ms   = [long]$lines[$timeHeader.LineNumber]

    if ($ms -le 0) {
        throw "Invalid execution time in $reportName"
    }

    $rate = $iret / ($ms / 1000.0)

    return [PSCustomObject]@{
        Processor = $Processor
        Run       = $Run
        IRet      = $iret
        TimeMs    = $ms
        Rate      = $rate
    }
}

$results = @()

foreach ($proc in @("RV32_ISS", "RV32_5S")) {

    Write-Host ""
    Write-Host "Testing $proc"

    for ($i = 1; $i -le $Runs; $i++) {

        $r = Measure-Rate -Processor $proc -Run $i
        $results += $r

        Write-Host ("Run {0}: {1:N0} instructions, {2:N0} ms, {3:N0} instr/s" -f `
            $i, $r.IRet, $r.TimeMs, $r.Rate)
    }
}

Write-Host ""
Write-Host "================ RESULTS ================"
Write-Host ""

$results | Format-Table `
    Processor, Run, IRet, TimeMs, `
    @{Name="InstrPerSec";Expression={[math]::Round($_.Rate)}} `
    -AutoSize

Write-Host ""

foreach ($proc in @("RV32_ISS", "RV32_5S")) {

    $rates = @(
        $results |
        Where-Object Processor -eq $proc |
        ForEach-Object Rate
    )

    $median = Get-Median $rates

    Write-Host ("{0} median rate = {1:N0} retired instructions/s" -f `
        $proc, $median)
}

$results | Export-Csv `
    (Join-Path $WorkDir "rate_measurements.csv") `
    -NoTypeInformation