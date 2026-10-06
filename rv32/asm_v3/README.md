# Assembly v3: return early for an already solved root

This is the second assembly refinement, based on assembly v2 at commit
`928e3c37370be0eb8fcfd54bb2f916aff02df168`. It retains the v2 depth-check
removal and changes only the solver's entry/exit handling.

## Change and correctness argument

Assembly v2 saves twelve callee-saved registers in a 48-byte frame, initializes
table bases, and computes the root heuristic before checking whether the
coordinates are already solved. Assembly v3 instead:

1. Rejects a null path pointer and out-of-range permutation/orientation
   coordinates using the same unsigned comparisons as v2.
2. Tests `p | o`. When it is zero, both coordinates are zero and `a0` already
   contains the return value, zero. The branch goes directly to the existing
   `ret` instruction after the normal epilogue, skipping both stack setup and
   restoration. It does not write an empty solution to the path buffer.
3. For a valid non-solved root, performs the existing 48-byte save, heuristic
   initialization and search. The search loop and replay remain unchanged.

The entry checks modify only the caller-saved temporary `t0`. Early returns
therefore preserve `sp`, `gp`, `tp`, and all `s` registers without saving them.
Invalid arguments still return -1, including a null path for a solved root.
Failures encountered after stack setup still use the normal restoring exit;
they must not jump to the new argument-error return.

The check uses general coordinates, not a particular input-string fixture.
Unchanged parsing still validates the 14-character input before the solver.

## Measurement hypothesis

The solved case should execute fewer instructions because it skips stack
stores/loads, base-address setup and heuristic lookup. Non-solved inputs still
perform the same argument and goal checks, now in a different order. Their
search work should be unchanged. Actual full-program instruction counts must
come from the pinned local Ripes run; none are claimed here before that run.

The new invalid-argument return replaces the old solved-result block while
the solved path shares the existing `ret`. The instruction audit checks the
resulting linked `.text`; code size is not inferred from source-line counts.

The general maximum call-stack requirement remains 80 bytes (32-byte target
harness plus 48-byte solver). The solved solver itself uses zero stack bytes;
the complete solved program still calls the parser and has a 48-byte maximum
by its call graph. The reserved 4,096-byte stack remains in the static budget.

## Build and measure in WSL

From `/home/evan/projects/minirubik`:

```sh
python3 rv32/asm_v3/build.py
python3 rv32/asm_v3/run.py
```

The build verifies preserved source and reference fingerprints. The runner
checks the Ripes binary against the saved GCC and assembly v2 environments,
checks source and ELF hashes, executes the three standard cases, and archives
raw reports with comparisons. Earlier versions are not rebuilt or remeasured.

- New build: `rv32/build/asm-v3/`
- New local evidence: `measurements/stage4-asm-v3/<run-id>/`
- GCC comparison: `comparison.json`
- Assembly v2 comparison: `comparison-v2.json`

The existing `--state` and `--expected` build options also support arbitrary
valid assembly-time inputs. The measurement runner accepts `--processor`
with `RV32_ISS` or `RV32_5S`; cross-version comparisons require matching inputs
and processor models. Official performance counts use the pinned `RV32_ISS`.

During the first build, Git HEAD names the preceding archive commit; source
hashes identify the new uncommitted files. After reviewing the actual local
results, commit this candidate and its evidence together.

This is a three-case target check, not the complete 2,644-state distance-11
gate. LED rendering and visual-pipeline validation remain pending. Consolidating
the shared build/run/validation tools and documenting the final entry point
in the root README remain deferred cleanup tasks.

## Optional supplementary validation

`python3 rv32/asm_v3/validate.py` requires Unicorn 2.1.4, pyelftools and host
`cc`. It is not required to run the WSL/Ripes measurement above.

The diagnostic validates full executables and 83 preserved solver samples
against exact BFS distances and independent cubie-level replay. It checks the
same solution paths and candidate counts as the preceding checkpoints,
preserved-register ABI rules and the existing depth invariant. Targeted
early-return tests check that solved and invalid-argument calls perform no
data-memory accesses and leave the stack and output untouched. Emulator
instruction visits are diagnostic only, not official Ripes retired counts.
