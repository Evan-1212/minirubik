# V2 native verification and comparison

**Decision: keep v2 as the next RV32I-port candidate; preserve v1 as the smaller
reference.** V2 reduces every measured distance-11 search count and is faster
in the paired native benchmark. Final adoption still requires target memory
and retired-instruction measurements. Neither C version has been certified
against the Ripes 50-million-instruction limit.

Baseline: `308da1e567eb0406e66b30a2c2927de525f9ca23`; v1 source commit `bfa7337`.
These results were measured in the ChatGPT Linux x86-64 execution environment,
not the student's WSL or Ripes. Source hashes and compiler details are in
`results/environment.json`.

## Measured comparison

Generated children and expanded frames are search counters, not instructions.
The extrema below are taken over all 2,644 distance-11 states.

| Metric | v1 | v2 |
| --- | ---: | ---: |
| Table payload, bytes | 40,383 | 122,184 |
| Native search frames, bytes | 144 | 144 |
| Minimum generated children | 140,895 | 7,278 |
| Median generated children | 191,727.5 | 16,514.5 |
| Maximum generated children | 639,792 | 109,629 |
| Maximum expanded frames | 106,635 | 18,273 |
| Total generated, all distance-11 states | 546,298,522 | 49,153,465 |
| Generated children for `21345671111111` | 233,961 | 35,847 |
| Expanded frames for `21345671111111` | 38,998 | 5,979 |
| Median native seconds, all distance-11 states | 3.995969 | 0.702679 |

Maximum generated children fall by 82.86%.
The paired uninstrumented native benchmark is 5.69x
faster by the ratio of median times. It warms up both solvers, alternates
order, and records five measured runs each. Both solvers are compiled in the
same executable, with identical `-O3` options and without stats macros.
The final paired timing run followed the exhaustive/sanitizer jobs; no other
solver verification job was deliberately run alongside it. Shared-host load
can still vary. Raw timings are in `results/native_benchmark.csv`.

The v2 generated-count worst case is `41532672313211`.
Full-domain verification found the same maximum. V1's corresponding worst
case is `54721631111111`. Neither is claimed to be the target's instruction
worst case. V2's distance-11 max/min generated-count ratio is 15.063x versus
v1's 4.541x: absolute work falls, but relative spread increases. This is not
an instruction-uniformity result. Every one of the 2,644 v2 per-state counts
is no larger than its v1 counterpart. Raw paths/counters are in
`results/hardest.csv` and `../optimized/results/distance11.csv`.

## Pattern selection

The host C sweep considered all 35 sorted choices of three out of seven cubies.
Every candidate solved and independently replayed all 2,644 distance-11 inputs.
The objective was lexicographic: minimize maximum generated children, then
sum, then cubie labels. It selected input labels **1, 2, 7**. The complete
sweep is in `results/pattern_sweep.csv`, with its progress in the matching log.
This selection does not optimize mean runtime or the still-unmeasured target
instructions directly. Other heuristic families were not exhaustively compared.

## Validation gates

| Check | Result |
| --- | --- |
| Independent physical-model BFS | PASS: all 3,674,160 states, diameter 11, exact histogram |
| H1 heuristic admissibility | PASS over all 3,674,160 states |
| Stronger or equal to v1 heuristic | PASS over all states; strictly stronger for 3,189,950 |
| H2 PDB completeness and exact abstract distances | PASS: 153,090 states; mixed maximum 9; one goal with value 0 |
| Permutation PDB | PASS: maximum 7, unique zero |
| Projection/move consistency | PASS for every permutation and all 9 moves |
| H4 packed versus raw byte distances | PASS: 76,440 odd + 76,650 even entries; 210 padding nibbles |
| Legal-input parser/rank agreement | PASS over all 3,674,160 states |
| H3 optimal length and original-model physical replay | PASS over all 3,674,160 states |
| H3 search + replay wall time | 70.543637 seconds, plus 0.159669 seconds oracle setup |
| All distance-11 cases | PASS: all 2,644 return optimal 11-move solutions |
| CLI contract | PASS: 9 solution vectors, 25 invalid cases per build, failed stdout detection |
| Instrumented/normal CLI agreement | PASS on the supplied CLI vectors |
| AddressSanitizer + UndefinedBehaviorSanitizer | PASS for `--check`; leak detection disabled |
| Ripes retired instructions / T5-T7 | NOT RUN |
| RV32I binary section and ISA audit | NOT RUN |

The full-domain instrumented run generated 4,708,611,241 children
in total. That is the whole host validation campaign, not one input.
Its wall time includes other host activity and is not used for the speedup
comparison. `results/exhaustive.json` and `results/exhaustive.log` record
completion and progress. The ASan/UBSan check excludes LeakSanitizer because
sandbox `/proc` access is restricted. See `results/sanitize.log`.

## Native memory observation

| Linked native section | Bytes |
| --- | ---: |
| `.rodata` | 122,539 |
| `.data.rel.ro` (pointer view) | 24 |
| `.data` | 8 |
| `.bss` | 224 |
| **Sum including `.data.rel.ro`** | **122,795** |
| Remaining to 128 KiB (131,072 bytes) | 8,277 |

Native `.text` is 2,571 bytes. Native section totals are not RV32I totals.
`results/native_audit.json` confirms linker garbage collection removes the
unused v1 solver, orientation-only PDB, and stats, and that host generators
are absent. Keep the section-GC flags when building. Measure the final linked
RV32I image again, counting all static data after target I/O integration.

## What remains before final submission

1. Reproduce native tests in the student's environment.
2. Port and run under RV32I/Ripes; audit ISA and linked static data.
3. Measure retired instructions for all 2,644 distance-11 cases, including
   `21345671111111`; verify the required 50-million limit with margin.
4. Complete the handwritten-assembly and GCC `-O2 -march=rv32i -mabi=ilp32`
   comparison, target replay, LED and pipeline requirements.
5. Prepare the English HackMD report using actual source/measurement evidence,
   and disclose AI assistance after the student's review and confirmation.

The C package is complete. These remaining items are target-port and submission
work, not unfinished native C verification. Nothing has been pushed to GitHub
or published to HackMD as part of this version.
