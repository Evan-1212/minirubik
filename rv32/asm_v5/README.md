# Assembly v5: reduce parser loop overhead

This is the fourth assembly refinement, based on assembly v4 at commit
`be10a162d6b822b5614ac5f18e0fb1f964d91f81`. The only changed runtime function
is `asm_parse`. The build links the archived v4 solver and the existing v1
replay and target harness, along with the same startup, linker script and tables.

## Change

The old parser performs several kinds of repeated work for every valid input:
it loads loop constants inside loops, calculates byte addresses from an index,
copies seven permutation bytes to the stack, and tests on every orientation
iteration whether the character contributes to the rank.

The new parser uses pointer traversal and holds the needed constants outside
the loops. It validates the seven permutation digits with the same bitset,
then rereads the original input bytes for the inversion counts. Their ASCII
ordering is the same as the ordering of validated digits after subtracting
`'1'`, so the counts remain identical. The six smaller-after counts and the
mixed-radix shift/add calculation are retained; no new ranking algorithm or
lookup table is introduced.

Orientation parsing now loops over exactly six digits to build the base-3
rank. The seventh digit is validated separately and added to the checksum.
The original modulo-three check and exact-length NUL check are retained.

All input reads finish before the final two output stores. A failed parse
leaves the output untouched. The local frame remains 16 bytes and now holds
only six inversion counts. No callee-saved register is modified, no helper
function is called, and the parser remains compatible with the existing ABI.
Input can start at an arbitrary byte address; the output must be suitably
aligned for the two uint16_t fields, as in the existing target harness.

## Why this targets small cases

Parsing runs once for every input, including solved and one-move states.
Reducing its fixed work should improve these cases without changing the
solver's search work. There are no fixture-specific checks or precomputed
answers. The full-program retired-instruction change must be measured using
the pinned local Ripes binary; this package does not claim those counts.

With GCC 13.2.0 and binutils 2.42, the complete linked `.text` is **1,428 bytes**,
down from v4's 1,444 bytes. Static data including the reserved 4,096-byte stack
remains **126,488 bytes**. The general call-graph stack maximum remains 80
bytes, or 48 bytes for a complete solved run. These maxima are distinct from
the stack reservation included in the static-data budget.

## Validation

The build checks the RV32I instruction set, memory budget, live runtime symbols
and preserved source/reference fingerprints. Only the parser is newly assembled
from this directory; the v4 solver is reused directly rather than copied.

The optional `validate.py` requires Unicorn 2.1.4, pyelftools and host `cc`.
It checks:

- All 5,040 permutation coordinates and all 729 orientation coordinates.
- All 2,187 combinations of orientation coordinate and seventh orientation digit.
- All 256 byte values at each of 15 positions, including the terminator:
  3,840 mutations compared against the native C parser.
- Early NULs and complete strings at the mapped-memory boundary, unaligned
  input, null arguments, output canaries and unchanged output on failure.
- Parser data accesses restricted to the input, 16-byte local frame and four
  output bytes, plus 21 aligned input/output overlap cases.
- Three complete executables and 83 parse/solve/replay samples checked against
  exact BFS distances, independent physical replay and preserved solution paths.
- ABI preservation and stack bounds on the direct calls.

These are supplementary development-environment checks, not official Ripes
instruction counts or exhaustive assembly search validation. The saved build
and validation reports are in `supplementary/`.

## Build and measure in WSL

From `/home/evan/projects/minirubik`:

```sh
python3 rv32/asm_v5/build.py
python3 rv32/asm_v5/run.py
```

The runner uses Windows Ripes at `C:\Tools\Ripes\Ripes.exe` and verifies its
SHA-256 against the archived GCC and v4 runs. The pinned version is
`v2.2.6-106-g5b8a616`, using `RV32_ISS` without extensions and with rendering
disabled. Counts include startup, parse, solve, replay, expected-length check
and exit ecall. Source and ELF hashes are checked before execution.

- New build: `rv32/build/asm-v5/`
- New local evidence: `measurements/stage4-asm-v5/<run-id>/`
- GCC comparison: `comparison.json`
- Assembly v4 comparison: `comparison-v4.json`

Previous versions are not rebuilt or remeasured. `build.py --state <state>
--expected <length>` supports arbitrary valid assembly-time inputs; omit
`--expected` if the length is unknown. `run.py --processor RV32_5S` is available
for later pipeline work; cross-version comparisons require matching inputs
and processor models. Official performance measurements use `RV32_ISS`.

Build provenance initially records the preceding archive commit. Source hashes
identify the newly added files used for the build. After reviewing the local
results, archive the candidate and its measurement evidence together.

The complete 2,644-state distance-11 performance test, LED rendering and visual
pipeline validation remain pending. Shared-tool consolidation and final root
README cleanup remain deferred.
