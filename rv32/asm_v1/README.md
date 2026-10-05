# Initial hand-written RV32I candidate (asm-v1)

This is the first implementation of `DESIGN.md`, ready for the author's Ripes
measurements. It is not a completed final submission. Preserve this version and
its first measurements before making subsequent assembly improvements.

## What is implemented

- `parse.S`: input validation and coordinate ranking, using a 16-byte local frame.
- `solve.S`: iterative IDA*, 12-byte explicit search frames, six existing tables,
  permutation-first pruning, and cached quarter-turn row addresses.
- `replay.S`: target-side solution replay and move/coordinate checks.
- `target.S`: test harness, result storage, and a 24-byte face-row descriptor.
- `build.py`: builds three ELF inputs, audits RV32I, data size, and live code symbols,
  and saves commands plus source/binary fingerprints.
- `run.py`: runs Windows Ripes from WSL, verifies the same Ripes binary as the
  archived GCC run, saves telemetry, and computes per-input GCC comparisons.

All runtime instructions are hand-written assembly. The only C objects linked
into the target contain the previously generated read-only tables. No C parser,
search, replay, or compiler arithmetic helper is linked. The existing startup,
linker script, GCC baseline sources, and previous measurements remain in place.

The scalar solver ABI is `asm_solve(p, o, path)` in a0/a1/a2, returning length in
a0. It differs from passing the C `v1_coord` struct by value. The routine is a
leaf, saves s0..s11 in 48 bytes, and restores them and sp before returning.
The harness uses 32 bytes; maximum stack use by this call graph is 80 bytes.
The linker still reserves and counts 4,096 bytes in the static budget.

A deliberate parser detail differs from the high-level design's unspecified
scratch allocation: its 16-byte local area holds seven permutation bytes and
six inversion counts. Fixed shift/add stages then combine the counts. There is
no variable multiply or divide.

## First build audit (not a Ripes performance result)

Built with riscv64-unknown-elf-gcc 13.2.0 and GNU binutils 2.42:

| Item | GCC reference | asm-v1 |
| --- | ---: | ---: |
| Entire linked .text, renderer absent | 1,856 B | 1,472 B |
| Static data including 4 KiB reserved stack | 126,476 B | 126,488 B |
| Remaining allowance below 131,072 B | 4,596 B | 4,584 B |

Code size decreases by 384 bytes (20.69%). Data increase by 12 bytes: the
24-byte face-row descriptor replaces the live 12-byte generic PDB pointer view.
Section alignment and the complete linked image are included in the audit.
Instruction counts are intentionally left to Ripes; none are inferred from
source size, native timing, or Unicorn execution.

## Run in the existing WSL repository

```sh
python3 rv32/asm_v1/build.py
python3 rv32/asm_v1/run.py
```

The runner expects the previously archived GCC run at:

`measurements/stage4-gcc/20261005T080153Z-RV32_ISS-ea1f92/`

New output goes to `measurements/stage4-asm-v1/<run-id>/`. The Windows executable
is the already established `C:\Tools\Ripes\Ripes.exe`. The three cases and
validation work match the GCC reference. Each complete run retires startup,
parsing, solving, replay, expected-length validation, and the exit ecall.

The final console lines include `AUDIT PASS`, `PASS`, `COMPARE`,
`ASM_V1_TARGET_SMOKE=PASS`, and the evidence directory. A negative instruction
reduction percentage means this first version retires more instructions for
that input; preserve and report it rather than optimizing before saving the
initial result. The compiler reference may win on a small input even when the
assembly improves the distance-11 case.

The optional `--processor RV32_5S` selects the pipeline model. This initial step
uses the default RV32_ISS. Pipeline validation, LED rendering, and all 2,644
distance-11 states remain later gates.

To build another valid input later:

```sh
python3 rv32/asm_v1/build.py --state 12345672221111
python3 rv32/asm_v1/run.py
```

Omitting `--expected` disables only the known-length assertion; parsing, actual
search, solution replay, and the 0..11 length range check still execute.
Re-run build.py with no arguments to return to the three standard cases.

## Supplementary validation already performed

`testing/validate_unicorn.py` executes the linked RV32 instructions using Unicorn
2.1.4 and checks them against a host BFS oracle built from the original cubie
moves. It also tests each assembly routine's ABI preservation. The saved report
and log in `supplementary/` describe this separate cloud environment; they are
not the author's local Ripes measurements.

The passing checks include:

- Three complete executables, target checks, and independent physical replay.
- Parser coverage of all 5,040 permutations and all 729 orientation coordinates
  (5,769 calls, with the solved combination appearing in both groups).
- Malformed strings, early-NUL reads at a mapped-memory boundary, and null pointers.
- Actual root heuristic instructions on all 210 PDB rows at orientation indices
  0, 1, 727, 728 (840 cases, including offsets above 65,535).
- 83 complete searches: supplied vectors, reproducible random states, coordinate
  boundaries, and known difficult inputs. Every length matches the exact BFS
  distance and every path solves the original cubie model.
- Callee-saved registers, sp, gp, and tp preserved on completed direct calls;
  invalid solve/replay arguments rejected; result-path boundary preserved.
- Stack writes reach exactly 80 bytes below the initial stack top in the three
  complete executable runs, agreeing with the call-graph allocation.

These tests do not establish exhaustive assembly correctness or replace Ripes.
Reproducing them is optional and requires `unicorn`, `pyelftools`, and a host C
compiler. The normal build/Ripes commands use only Python's standard library
and the RISC-V tools already installed on the author's machine.

## Evidence and next step

`baseline-files.json` fingerprints the unchanged GCC baseline and table sources.
The build checks these before compilation and records its actual Git HEAD and
hashes, including new uncommitted files. The runner checks source and ELF hashes
again before measuring. Preserve the resulting source, maps, disassembly,
audits, raw Ripes JSON, summary, and comparison as one initial assembly milestone.

After the local three-case measurement passes, archive that milestone with a
commit and push, then update the English Stage 4 report with the real numbers.
No new algorithmic or register-caching optimization has been applied after the
first executable was validated. Rendering and later optimization work remain
separate steps. The AI disclosure text remains pending discussion.
