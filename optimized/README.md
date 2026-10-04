# Optimization v1: iterative IDA* with separate coordinate PDBs

This is the first C comparison implementation (candidate A), based on
`Evan-1212/minirubik` commit `308da1e567eb0406e66b30a2c2927de525f9ca23`.
The original `solver.c`, `mini.c`, root Makefile, and Stage 1 measurements
are unchanged. This version is not the final HW1 submission or RV32I assembly.

## Build and run

In Ubuntu/WSL, from the repository root (requires a C99 compiler, make,
and Python 3 for CLI tests):

```sh
make -C optimized
./optimized/build/solver-v1 21345671111111
./optimized/build/solver-v1 --self-test
./optimized/build/solver-v1-stats 21345671111111
make -C optimized check
make -C optimized hardest
make -C optimized exhaustive
```

The normal executable writes only an optimal move sequence and a newline.
The solved cube prints an empty line. Invalid input returns status 2;
internal verification or output failures return status 1.
The stats executable writes the same solution to stdout and counters to stderr.
Multiple shortest solutions can exist: a correct path need not match the
baseline's exact move string.

If copying into an existing checkout, copy the complete `optimized/` directory
next to `solver.c`; do not copy only `v1.c`. The host generator and verifier
deliberately reuse the pinned baseline's physical cube model through
`host_reference.h`. Keep its parent `solver.c` at the documented baseline
while reproducing these results.

## Files

| File | Purpose |
| --- | --- |
| `v1.c`, `v1.h` | Parser, factored coordinates, explicit-stack IDA*, replay; no libc dependency in the core |
| `cli.c` | Native CLI, three built-in tests, checked output |
| `generate_tables.c` | Host-only C generator for transitions and exact abstract distances |
| `v1_tables.c` | Deterministically generated read-only tables, included for inspection/reuse |
| `host_reference.h` | Host-only adapter to the unchanged original `solver.c` |
| `verify.c` | Host BFS oracle, H1/H2, exhaustive optimality and physical replay, hard-case statistics |
| `test_cli.py` | CLI input/output checks and a separate array-based physical replay |
| `results/` | Raw measurements and validation summaries from the documented execution environment |

`make clean` inside this directory removes only `build/`. A new build
regenerates `v1_tables.c` using the host compiler. The generator and full BFS
oracle are never linked into `solver-v1`.

## Design contract

- Preserve permutation rank `p` and orientation rank `o` separately.
- Use three quarter-turn transition tables for each coordinate.
- Generate each face's three siblings by successive quarter-turn lookups;
  each sibling still costs ONE HTM move from its parent.
- Use `max(permutation_distance[p], orientation_distance[o])` as a lower bound.
- Search integer IDA* thresholds beginning at that bound, up to diameter 11.
- Skip the immediately preceding face. Two adjacent same-face turns can
  combine or cancel, so no shortest path requires them.
- Use fixed-size frames and iterative control flow: no recursive search,
  heap allocation, floating point, or full-state target distance table.
- The solver core uses shifts/adds and explicit ranges instead of multiply,
  divide, or remainder operators. Host tools may use those operations.
- Stats are a host-only diagnostic option. Without `V1_STATS`, counters and
  64-bit counter operations are absent. The shared static frames make the
  solver non-reentrant; each parallel host worker must be a separate process.

Projection of a full solution solves each coordinate abstraction, so each PDB
distance is a lower bound. Their maximum is a lower bound as well. The search
only prunes when `depth + h > threshold`, and consecutive same-face pruning
preserves all shortest paths. Increasing thresholds therefore finds a shortest
solution. The complete-state goal test checks BOTH `p == 0` and `o == 0`.
The host tests additionally verify this argument against every exact distance.

## Data budget

| Object | Bytes |
| --- | ---: |
| Permutation quarter-turn transitions: 3 x 5040 x 2 | 30,240 |
| Orientation quarter-turn transitions: 3 x 729 x 2 | 4,374 |
| Permutation PDB: 5040 x 1 | 5,040 |
| Orientation PDB: 729 x 1 | 729 |
| Tables subtotal | 40,383 |
| 12 search frames (observed native layout) | 144 |
| CLI solution path | 11 |
| Subtotal of these objects | 40,538 |

This subtotal excludes alignment, strings, test constants and platform/runtime
data. `results/native_size.txt` records the native executable's actual sections;
it is not an RV32I section measurement. Final `.data + .bss + .rodata` must be
measured again on the linked target binary, including all other static data.
V1 uses byte PDBs, so nibble-accessor gate H4 is not applicable.

## Validation and measurements

`make check` checks H1 over all 3,674,160 states, both PDBs and every quarter-turn
table entry (H2), all legal input ranks, sample solutions, malformed inputs,
and unwritable stdout. PDB checks include a descending neighbor for every
non-goal entry and the Bellman edge inequalities, using oracle transitions.

`make exhaustive` checks the length AND independently replays the moves with
the baseline cubie model for all 3,674,160 states (H3). The oracle rebuilds its
own nine-move transitions from `apply_move`; it does not use the generated v1
arrays. Its BFS histogram must match all twelve known distance levels.
The exhaustive executable enables host counters; the CLI test checks that
instrumented and uninstrumented builds agree on every supplied vector.

`make hardest` covers all 2,644 distance-11 states. To write a per-state CSV:

```sh
./optimized/build/verify-v1 --hardest optimized/results/distance11.csv
```

Counter definitions (summed across threshold iterations):

- `generated`: each candidate child actually produced by the two transition
  lookups, including children rejected by the bound; same-face skips excluded.
- `expanded`: each non-goal frame entered to enumerate children, including
  a fresh root for each threshold; pruned children and goal leaves excluded.
- `pruned`: generated children rejected by the depth/heuristic bound.

These are algorithm counters, NOT retired instructions. In particular,
`generated` and `expanded` must not be compared as if they were the same metric.
`distance11_summary.json` identifies the worst case by generated children;
the Ripes-instruction worst case may be different.

Optional memory/undefined-behavior check:

```sh
make -C optimized sanitize
```

In the ChatGPT sandbox LeakSanitizer could not inspect `/proc` at process exit.
The recorded ASan/UBSan run therefore uses `ASAN_OPTIONS=detect_leaks=0`.
Leak checking is not claimed by that run; address and undefined-behavior checks
remain enabled. The existing signedness warning comes from the unchanged
baseline included by host tools, not from the v1 core.

All recorded host timings were obtained in the ChatGPT Linux execution
environment described in `results/environment.json`, not on Evan's laptop.
No timings or counters here may be relabeled as the user's own Ripes results.

## Remaining work and disclosure reminder

- Choose/measure stronger PDB configurations if useful; v1 is the baseline
  for that comparison, not a claim that candidate A is the final design.
- Compile the final C for RV32I and inspect all instructions/helper references.
- Write/refine hand-written RV32I and compare with GCC `-O2 -march=rv32i
  -mabi=ilp32` using target instruction counts and linked `.text` bytes.
- Run T5-T7 in the pinned Ripes build; measure EVERY distance-11 state with
  rendering disabled and separately report `21345671111111`.
- Implement LED visualization and the pipeline walkthrough.
- Update the English HackMD incrementally; retain code/results in Git.
- Before submission, remind Evan to confirm the instructor's in-class AI
  permission and accurately disclose AI assistance. This implementation,
  host tools, tests, and documentation were AI-assisted. Keep the recorded
  execution environment attached to every measurement.

The remaining RV32I limits, visualization, and submission requirements are
not marked passed by a native C result.
