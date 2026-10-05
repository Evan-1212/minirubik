# Assembly v2: remove a redundant candidate-depth branch

This is the first measured-refinement candidate after assembly v1, not C Version 2.
The only runtime source change is the removal of `bltu s3, a1, .Lsolve_loop`
from the candidate loop in `solve.S`. All other runtime sources and tables are
reused from the preserved references. Build/run scripts give this candidate
separate artifacts and measurement archives.

## Why the branch is redundant

At every candidate-generation point, `0 <= depth < bound <= 11`:

1. A solved root returns before the search loop. For a valid non-solved root,
   the initial maximum heuristic is at least one: permutation distance is
   zero only for permutation coordinate zero; when that coordinate is zero,
   the mixed abstraction retains the complete orientation and has zero
   distance only for solved orientation. Thus the root starts at depth zero
   below a positive bound.
2. A child frame is created only after the existing `bgeu a1, s3` test has
   established `child_depth < bound`.
3. Moving to another sibling does not change the current depth; backtracking
   reduces it. The next threshold increases the bound and restarts at zero.

Consequently `child_depth = depth + 1 <= bound`. The removed unsigned branch
can never be taken, and the subsequent `bound - child_depth` cannot underflow.
The existing descent check remains. No move order, pruning heuristic, solution
path, or table layout changes.

This reasoning depends on the validated heuristic tables and normal internal
control flow. It does not assume arbitrary corrupted table or frame contents.

## Expected effect, before local Ripes measurement

One RV32I instruction (4 bytes of linked `.text`) is removed. Each generated
candidate executes one fewer instruction. A solved input generates no
candidates, so no instruction-count improvement is expected for that input.
Measured local Ripes counts must be recorded before claiming an improvement
in the report; emulator diagnostics are kept separate.

## Build and measure in WSL

From `/home/evan/projects/minirubik`:

```sh
python3 rv32/asm_v2/build.py
python3 rv32/asm_v2/run.py
```

The build checks preserved reference-source fingerprints. The runner verifies
that the Ripes executable matches both saved reference runs, verifies source
and executable hashes, runs solved/short/distance11, and saves raw reports.
It compares with GCC and with the already measured assembly v1, without
rebuilding or rerunning either reference.

- New build directory: `rv32/build/asm-v2/`
- New local evidence: `measurements/stage4-asm-v2/<run-id>/`
- GCC comparison: `comparison.json`
- Assembly v1 comparison: `comparison-v1.json`

The new source is uncommitted during measurement, so provenance records the
current Git HEAD plus hashes of the exact source used. Commit the candidate
and its actual local evidence together after reviewing the results.

This three-case run is not the full 2,644-state distance-11 performance gate.
LED rendering and visual-pipeline validation remain separate pending work.

## Optional supplementary diagnostic

`python3 rv32/asm_v2/validate.py` requires Unicorn 2.1.4, pyelftools and host `cc`.
It checks this specific change against the preserved v1 sample paths, exact
BFS distances, physical replay, ABI preservation, and the depth invariant at
each generated candidate in those runs. It is not required for the WSL Ripes
measurement and produces no official Ripes instruction counts.
