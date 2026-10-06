# Assembly v4: keep active search state in registers

This is the third assembly refinement, based on assembly v3 at commit
`75bbda752b6d6e98e324268aaabbc6cbb62cbcd2`. It retains the removed depth check
and solved-root early return. Only the solver's search-state storage changes.
The parser, replay, target harness, startup, linker script and tables are reused.

## Change

The v3 loop reads the current face, previous face, next turn and two cursor
coordinates from its static frame. It writes the advanced cursor and turn
back even when the candidate is immediately pruned. In v4, these five values
remain in caller-saved registers throughout the active frame:

| Register | Active value |
| --- | --- |
| `t2` / `t3` | Current permutation / orientation cursor |
| `a3` | Face, 0 through 3 (3 means exhausted) |
| `a4` | Next turn index, 0 through 3 |
| `a5` | Previous face, or 3 at the root |

The two transition lookups advance the cursor in place. The face and turn
produce the same move ID, and the turn is advanced before heuristic pruning
or descent. The two face/turn end checks also share the constant 3 already
available in `t1`, instead of loading that constant again after a frame read.

Before actual descent, the solver stores the parent's five continuation
values into the existing frame slots. The child starts with the candidate
coordinates, face 0, turn 0 and the parent's face as its previous face.
On backtrack, the solver reloads the five saved values and selects the parent's
transition rows again. It still resets the cursor from the frame's base
coordinates when changing faces.

The static frame format stays at 12 bytes, with 12 frames reserved:
`p=0`, `o=2`, `cursor_p=4`, `cursor_o=6`, `face=8`, `turn=9`, `prev=10`.
**Only base `p/o` are authoritative in the active frame.** Its continuation
slots may be stale until descent. Suspended parent frames have complete saved
continuations. No code reads an active frame's stale continuation slots.

## Correctness and ABI

- Threshold initialization establishes the root cursor and control state.
- Every candidate advances the cursor and next-turn index, including candidates
  rejected by either heuristic. Subsequent siblings therefore retain the same
  quarter-turn sequence as v3.
- Saving before descent captures the already-advanced parent. Restoring it
  resumes with the next sibling, including the turn-3/next-face boundary.
- Changing faces restores the base coordinates, and the previous-face test
  retains the same pruning. Descriptor access still excludes exhausted face 3.
- The depth invariant remains `0 <= depth < bound <= 11` at candidate creation.
  Search order, thresholds, heuristics, move IDs and goal tests are unchanged.
- The solver is a leaf: it makes no calls that could clobber these caller-saved
  registers. It retains the same 48-byte, 16-byte-aligned save area and restores
  `s0..s11`. Solved and invalid-argument early returns remain unchanged.

This trades frequent active-frame memory access for five stores on descent
and five loads on backtrack. It is a storage optimization, not a stronger
heuristic or a different search algorithm. Benefits must be measured; the
saved/restored state does add work on descent and backtrack.

## Build audit and supplementary checks

With GCC 13.2.0 and binutils 2.42, each of the three complete linked executables
has **1,444 bytes of `.text`**, down from v3's 1,468 bytes. Static data including
the reserved 4,096-byte stack remains **126,488 bytes**. The instruction audit
checks RV32I and permits only the five hand-written runtime function symbols.
No runtime C search implementation or arithmetic helper is linked.

The call-graph stack maximum remains 80 bytes for non-solved search and 48 bytes
for a complete solved run; the solved solver itself uses no stack. These maxima
are separate from the reserved 4,096 bytes included in the static budget.

`python3 rv32/asm_v4/validate.py` uses Unicorn 2.1.4, pyelftools and host `cc`.
It is supplementary and is not required for the local Ripes command below.
It checks the three full executables and the 83 preserved solver samples
against exact BFS distances and independent cubie-level replay. Paths and
candidate counts must match the archived versions. It checks ABI preservation,
path bounds, candidate depth and cursor invariants, and saved/restored parent
continuations at every sampled descent/backtrack. Coverage includes all nine
face/turn combinations, descent after turns 1/2/3, and threshold increases.
Ten solved/invalid-argument checks retain the zero-data-access early-return
contract. Repeated calls reuse the workspace, so stale frame contents cannot
be relied on. The build and validation records are in `supplementary/`.

These checks are not exhaustive assembly validation, official Ripes instruction
counts, or the complete 2,644-state distance-11 gate.

## Build and measure in WSL

From `/home/evan/projects/minirubik`:

```sh
python3 rv32/asm_v4/build.py
python3 rv32/asm_v4/run.py
```

The build verifies preserved source/reference fingerprints. The runner checks
source and ELF hashes, and verifies that the Windows Ripes binary matches the
archived GCC and v3 runs. It uses the pinned `v2.2.6-106-g5b8a616` binary at
`C:\Tools\Ripes\Ripes.exe` with `RV32_ISS`, no extensions and rendering disabled.
The full count covers startup, parse, solve, replay, expected-length check and
exit ecall. Earlier builds and measurements are not rerun.

- New build: `rv32/build/asm-v4/`
- New local evidence: `measurements/stage4-asm-v4/<run-id>/`
- GCC comparison: `comparison.json`
- Assembly v3 comparison: `comparison-v3.json`

No local Ripes counts are claimed before that run. For a custom valid state,
use `build.py --state <14-character-state> --expected <known-length>`; omit
`--expected` if the length is unknown. The runner also accepts `--processor
RV32_5S`; cross-version comparisons require matching inputs and processor
models. Official performance measurements use the pinned `RV32_ISS`.

Build provenance names the preceding archive commit while source hashes identify
the new, initially uncommitted files. After reviewing local results, archive
this version and its evidence together. Keep the old versions intact.

LED rendering, visual-pipeline validation and the full distance-11 performance
gate remain pending. Shared-tool consolidation and final root README cleanup
remain deferred; this version does not reorganize historical source or evidence.
