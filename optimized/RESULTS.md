# V1 native verification results

Baseline: `308da1e567eb0406e66b30a2c2927de525f9ca23`.
Environment and source hashes: `results/environment.json`.
These are native Linux C measurements made in the ChatGPT execution environment.
They are not Evan's WSL or Ripes measurements.

| Check | Result |
| --- | --- |
| Full BFS oracle | 3,674,160 states; diameter 11; all distance-level counts matched |
| H1: admissibility | PASS over all 3,674,160 states |
| H2: tables | PASS; permutation max 7, orientation max 6; solved entries 0 |
| Legal-input parser/rank agreement | PASS over all 3,674,160 states |
| H3: optimal length and independent physical replay | PASS over all 3,674,160 states |
| H3 search/replay wall time | 377.218686 seconds (excludes oracle setup) |
| H3 oracle setup wall time | 0.104301 seconds |
| All distance-11 cases | PASS: 2,644 optimal 11-move solutions and physical replays |
| CLI checks | 9 solution vectors and 25 rejection cases per build; stdout failure checked |
| ASan/UBSan | PASS for `--check`; LeakSanitizer disabled due sandbox `/proc` restriction |
| H4 | Not applicable: byte tables, no nibble packing |
| Ripes T5-T7 / retired instructions | NOT RUN |
| RV32I static data / instruction-set audit | NOT RUN |

## Search counters

Counters include all IDA* threshold iterations. They are not CPU instructions.
Every child that is generated incurs work, including heuristic-pruned children.

| Input set | Generated children | Expanded frames |
| --- | ---: | ---: |
| `21345671111111` | 233,961 | 38,998 |
| Maximum over all distance-11 states | 639,792 | 106,635 |
| Maximum over the complete domain | 639,792 | 106,635 |

The generated-child worst case is `54721631111111`. Distance-11
minimum/median/maximum generated children are 140,895 / 191,727.5 /
639,792. Maximum/minimum is 4.541x. No claim is made that this
input also maximizes retired instructions.

Raw per-state data and actual solutions are in `results/distance11.csv`.
The exhaustive run generated 59,422,039,981 children in total;
that number describes the entire host verification campaign, not one query.

## Memory

Tables: 40,383 bytes. Search workspace: 144 bytes on the measured native build.
The solution path is 11 bytes. Strings, alignment, and platform data add to
those figures. The native executable has `.data` 16, `.bss` 224 and `.rodata`
40,747 bytes: a total of 40,987 bytes for those three sections. Its linked
`.text` is 2,490 bytes. These x86-64 values are included only as native build
observations; they do not certify the target budget or assembly code size.

## Reproduce

From the repository root:

```sh
make -C optimized check
./optimized/build/verify-v1 --hardest optimized/results/distance11.csv
make -C optimized exhaustive
ASAN_OPTIONS=detect_leaks=0 make -C optimized sanitize
```

The full-domain run enables host counters. Instrumented and uninstrumented CLI
builds are separately compared on the supplied vectors. Timing varies by host
and load; v1 is a correct first comparison version, not proof of the target
50-million-instruction requirement.
