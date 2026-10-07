# Measurement and validation index

[Repository home](../README.md) · [RV32I guide](../rv32/README.md)
· [HackMD report](https://hackmd.io/TMhkNvaMTGOpdAZwlM0ZgA)

Start with each summary; the adjacent raw records preserve the corresponding
environment, input, output and provenance. Historical run directories are
kept intact. Their timestamps identify runs, not the date of this index.

## Host and simulator characterization

| Stage | Evidence | What it establishes |
| --- | --- | --- |
| Stage 1: host memory expansion | [Memory CSV](memory_measurements.csv), [summary](memory_summary.txt), [script](measure_memory.ps1) | Host bytes per guest byte on the measured installation |
| Stage 1: simulator rate | [Rate CSV](rate_measurements.csv), [script](measure_rate.ps1), [loop](measure_rate.s) | Retired-instruction rates for the selected models and workload |
| Initial C checks | [2026-10-04 archive](2026-10-04-native-check/) | Native v1/v2 checks and environment |
| Exhaustive C H3 | [2026-10-05 archive](2026-10-05-native-h3/) | All 3,674,160 states checked for shortest length and physical replay, for both C variants |
| Stage 3 comparison | [Summary](2026-10-05-stage3/stage3-summary.json), [benchmark](2026-10-05-stage3/native-benchmark.csv), [full archive](2026-10-05-stage3/) | Native timings, candidate counts and v1/v2 distance-11 records |

Native timings and exhaustive C results do not substitute for target assembly
measurements or correctness checks. The report explains each measurement's scope.

## Renderer-free Windows RV32I measurements

These records use the pinned Windows Ripes `v2.2.6-106-g5b8a616`, `RV32_ISS`
with no ISA extensions. Counts include startup, parsing, search, replay,
expected-length validation and exit. Linked `.text` and static data are
reported separately; the reserved 4,096-byte stack is included in static data.

| Implementation | Three-case summary | Full run directory |
| --- | --- | --- |
| GCC reference | [CSV](stage4-gcc/20261005T080153Z-RV32_ISS-ea1f92/summary.csv) | [GCC](stage4-gcc/20261005T080153Z-RV32_ISS-ea1f92/) |
| Assembly v1 | [CSV](stage4-asm-v1/20261005T161528Z-RV32_ISS-868472/summary.csv) | [v1](stage4-asm-v1/20261005T161528Z-RV32_ISS-868472/) |
| Assembly v2 | [CSV](stage4-asm-v2/20261005T171457Z-RV32_ISS-41921a/summary.csv) | [v2](stage4-asm-v2/20261005T171457Z-RV32_ISS-41921a/) |
| Assembly v3 | [CSV](stage4-asm-v3/20261006T023824Z-RV32_ISS-fb2518/summary.csv) | [v3](stage4-asm-v3/20261006T023824Z-RV32_ISS-fb2518/) |
| Assembly v4 | [CSV](stage4-asm-v4/20261006T032552Z-RV32_ISS-b5f010/summary.csv) | [v4](stage4-asm-v4/20261006T032552Z-RV32_ISS-b5f010/) |
| Assembly v5 | [CSV](stage4-asm-v5/20261006T085548Z-RV32_ISS-051199/summary.csv) | [v5](stage4-asm-v5/20261006T085548Z-RV32_ISS-051199/) |

The earlier [v5 run](stage4-asm-v5/20261006T083314Z-RV32_ISS-fe447c/) is also
retained. Consult each run's own reports and environment before comparing it.

## Complete distance-11 target gate

The [full summary](stage4-asm-v5-distance11/20261006T114648Z-RV32_ISS-0d1d38/summary.json)
records **2,644 / 2,644 PASS**, with a maximum of **4,391,914 retired
instructions** for `41532672313211`, below the 50,000,000 limit. The runtime
has 1,428 `.text` bytes and 126,488 static-data bytes.

- [All per-state measurements](stage4-asm-v5-distance11/20261006T114648Z-RV32_ISS-0d1d38/summary.csv)
- [Raw reports, attempts, success records and audited template](stage4-asm-v5-distance11/20261006T114648Z-RV32_ISS-0d1d38/)
- [Reproduction and resume instructions](../rv32/distance11/README.md)

This archive accounts for most of the repository's file count. It retains
input assembly, launch logs, raw reports and per-case results, while sharing
one template ELF and common build records. Empty launch logs are retained as
part of the recorded attempts. No full remeasurement is needed merely to read
the completed results. The test covers the entire distance-11 shell, not all
3,674,160 states on the target.

## LED integration and visual pipeline

| Evidence | Scope |
| --- | --- |
| [New-artifact Windows CLI reports](../rv32/led/supplementary/windows-cli/20261007-160248/) | Renderer-free ELF counts: 557 / 753 / 1,468,209 for solved / short / required vector |
| [Windows GUI observations](../rv32/led/supplementary/windows-gui/WINDOWS_GUI.md) | Actual 35×25 LED peripheral, completion registers and sampled animation captures |
| [Integration guide](../rv32/led/README.md) | Shared renderer switch, memory audits, three-case RV32_5S results and evidence limitations |
| [Pipeline walkthrough](../rv32/led/supplementary/windows-pipeline/20261007/WALKTHROUGH.md) | Clock-stepped startup store, memory-write controls, jump flush and register writeback |
| [Supplementary checks](../rv32/led/supplementary/) | Linux/Unicorn checks, geometric comparisons and build audits, distinct from Windows measurements |

The solved and distance-11 final-display PNG files are identical archived
copies, not independent captures; see the integration guide. Initial and
move-5 distance-11 captures and the observed 12-frame sequence have their own
documented scope. The startup walkthrough is not a complete-solver timing run.

## Preserving and reproducing evidence

The C result CSV files also retained under `optimized/results/` and
`optimized_v2/results/` serve their original checkpoint documentation. Similar
files in different measurement directories may belong to separate runs.
Historical copies, environment records, manifests and hashes are preserved.

The final runtime still imports earlier version files, and build/resume checks
fingerprint historical sources and some documentation. In particular, do not
edit old guides or consolidate their scripts merely to remove repeated text.
Current navigation and completion status live in this index and the RV32I
guide; pending-work descriptions inside preserved checkpoint documents refer
to their original stage. Generated working builds belong in ignored build
directories, whereas intentionally archived artifacts stay with their evidence.
