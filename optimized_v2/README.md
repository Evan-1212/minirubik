# Optimization v2: iterative IDA* with a packed mixed PDB

This is a complete **native C comparison version** built on v1. Keep v1 as
the smaller-memory reference. V2 is a candidate for the RV32I port, not a
completed Ripes or assembly submission. Measured results and remaining gates
are in [RESULTS.md](RESULTS.md).

The baseline is `Evan-1212/minirubik` commit
`308da1e567eb0406e66b30a2c2927de525f9ca23`. Original files and `optimized/`
are unchanged. This directory depends on `../optimized/` and `../solver.c`.

## Build and run

From the repository root, using Ubuntu/WSL with a C99 compiler, make,
Python 3, and binutils:

```sh
make -C optimized_v2
./optimized_v2/build/solver-v2 21345671111111
./optimized_v2/build/solver-v2-stats 21345671111111
make -C optimized_v2 check
make -C optimized_v2 hardest
make -C optimized_v2 exhaustive
```

When adding this to an existing checkout, copy both `optimized/` and
`optimized_v2/` alongside the pinned `solver.c`. Preserve any local changes
in your checkout. Alternatively, build directly in the extracted archive.

Stdout contains an optimal solution followed by a newline; solved input prints
an empty line. Invalid input exits 2, and internal/output failure exits 1.
The stats executable produces the same stdout and prints counters on stderr.
Do not compare optimal move strings for equality across v1 and v2: multiple
shortest paths can exist. Check length and replay.

## What changed

V2 keeps v1's full permutation and orientation coordinates, quarter-turn
transition tables, move order, explicit search stack, and same-face pruning.
It changes the lower bound to:

```text
h(p,o) = max(permutation_distance[p], mixed_distance[projection[p],o])
```

The mixed abstraction remembers the labeled positions of input cubies
**1, 2, and 7**, plus the complete orientation coordinate. It has
`7 * 6 * 5 * 729 = 153,090` states. It omits the identities of the other four
cubies and is not the prohibited full-state target distance database.

The host C generator enumerates the 210 ordered placements, constructs
abstract transitions, and runs BFS. Distances fit in four bits (observed
maximum 9). Each 729-entry row takes 365 bytes; the unused final high nibble
is sentinel 15. Runtime lookup uses a permutation-to-placement byte table,
precomputed row offsets, shifts, and masks. Target code does not perform
runtime multiplication or division to locate a nibble.

Before reading the mixed PDB for a child, the search checks the cheaper
permutation bound. If it already exceeds the remaining depth, the mixed
lookup is skipped. This is equivalent to pruning by the maximum of the two
bounds. The goal test still checks the complete `p == 0 && o == 0` state.

All 35 sorted three-cubie subsets were evaluated on all 2,644 distance-11
states. Selection minimizes the largest number of generated children, then
the sum, then lexicographic order. `pattern.txt` records the selected input
labels, and `results/pattern_sweep.csv` preserves all measurements. This is
a choice within this design family, not a claim of globally optimal design
or the best RV32I instruction count.

## Correctness contract

A physical move induces a well-defined move on the selected positions and
orientation. Projecting a physical solution produces an abstract solution,
so the exact abstract distance cannot exceed the true distance. Taking its
maximum with the full permutation distance remains admissible. Full-domain
testing also confirms that this bound is never weaker than v1's.

IDA* tries integer thresholds starting at this lower bound, up to diameter 11.
The complete search and same-face pruning are inherited from v1. Two adjacent
turns of the same face combine or cancel, so omitting them preserves shortest
paths. A returned solution therefore has minimum HTM length. The host BFS
oracle and physical replay additionally verify this over every legal state.

Target search uses no recursive calls, heap allocation, floating point, or
full-state distance table. The static frames make each solver non-reentrant.
Diagnostic 64-bit counters are compiled only with `V2_STATS`; do not enable
them for the RV32I production build or instruction comparisons. Passing an
arbitrary custom `v2_pattern` requires correctly sized, valid tables; it is
a trusted generated-data interface, not an external-input validator.

## Memory and linking

| Live table | Bytes |
| --- | ---: |
| Full permutation quarter-turn transitions | 30,240 |
| Full orientation quarter-turn transitions | 4,374 |
| Full permutation PDB | 5,040 |
| Full permutation to selected placement | 5,040 |
| Placement row offsets | 840 |
| Mixed PDB, row-wise nibble packing | 76,650 |
| **Table payload** | **122,184** |

Search frames take 144 bytes on the measured native ABI; the path is 11 bytes.
This payload subtotal excludes alignment, strings, the pointer view (24 bytes
on the native ABI), and platform data. See `results/native_size.txt` and
`results/native_audit.json` for actual linked native sections. The pointer
view can be placed in `.data.rel.ro`, which the audit also counts.

The Makefile uses `-ffunction-sections -fdata-sections -Wl,--gc-sections`.
This is part of the build contract: it removes v1's unused orientation-only
PDB and search frames, despite reusing v1's parser, transitions, and replay.
`audit_native.py` checks this and the native static-data budget. Host BFS,
generators, and uncompressed mixed distances are never linked into the CLI.
The final RV32I image must be measured again after adding its I/O and other
static objects; a native size observation does not certify that target.

## Validation and reproduction

`make check` covers the CLI, every legal parser/rank pair, all transition
entries, H1 admissibility over 3,674,160 states, H2 abstract completeness and
shortest-distance properties, and H4 packed/unpacked equality for all 153,090
entries. It checks both even/odd nibble indices and every padding nibble.
Projection/move consistency is checked for every full permutation and move.
The oracle rebuilds nine-move transitions from the original physical model,
independently of generated target arrays, and verifies the full distance
histogram. `make exhaustive` checks H3 optimal length and physical replay for
every legal state. Host oracle allocations are outside target code.

```sh
# Save per-state distance-11 counters and paths.
./optimized_v2/build/verify-v2 --hardest optimized_v2/results/hardest.csv

# Reevaluate all 35 subsets; compare the winner with pattern.txt.
make -C optimized_v2 sweep

# Native timing only: uninstrumented v1/v2, warm-up, then five paired runs.
make -C optimized_v2 benchmark

# Address/undefined-behavior checks, with leak detection disabled.
make -C optimized_v2 sanitize
```

The benchmark builds inputs and the oracle outside timing, alternates run
order, and times solving all 2,644 distance-11 inputs with both solvers in
one executable, compiled with the same options and no stats macros.
Sanitizer checks use `ASAN_OPTIONS=detect_leaks=0` because this execution
environment restricts `/proc` access. This does not certify leak checking.
The baseline physical model has an existing signedness warning at
`solver.c:133`; this version does not change the baseline to suppress it.

## Source map

| File | Purpose |
| --- | --- |
| `v2.c`, `v2.h` | Iterative solver, packed heuristic accessor, optional counters |
| `v2_tables.c`, `pattern.txt` | Generated target tables and selected cubies |
| `generate_tables.c`, `pattern_build.*` | Host C abstract-table generator |
| `select_pattern.c` | Host comparison of all 35 subsets |
| `host_oracle.h`, `verify.c` | Independent BFS oracle and exhaustive validation |
| `cli.c`, `test_cli.py` | Native interface and CLI/replay checks |
| `benchmark.c` | Paired uninstrumented native timing |
| `audit_native.py` | Linked-section and unused-symbol checks |
| `results/` | Raw results, logs, environment and source hashes |

## Remaining assignment work and AI disclosure

Ripes RV32I execution, target data-section/instruction-set audits, retired
instructions over every distance-11 input, handwritten assembly, comparison
with GCC `-O2 -march=rv32i -mabi=ilp32`, target replay/LED/pipeline checks, and
the final English HackMD report remain to be completed. Use the teacher's
current specification to check these gates; native counters are not retired
instructions. No GitHub push or HackMD publication is included in this package.

AI assistance to disclose: Codex assisted with the implementation, host test
tools, experiment execution, and draft documentation. The student still needs
to review and understand the generated work. The student reports that the
instructor permits AI use with understanding; final confirmation and accurate
disclosure remain on the submission checklist. Do not claim these native runs
were performed on the student's WSL machine or on Ripes.
