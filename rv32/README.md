# RV32I implementation and validation

[Repository home](../README.md) · [Measurement index](../measurements/README.md)
· [HackMD report](https://hackmd.io/TMhkNvaMTGOpdAZwlM0ZgA)

## Current entry points

The final runtime combines the **v5 parser**, **v4 search**, **v1 replay**,
common startup/linker script and the C-generated tables. The LED integration
adds its own target driver and renderer. The earlier directories are required
by these builds; version numbers identify refinements, not standalone copies.

| Goal | Command from the repository root | Guide / output |
| --- | --- | --- |
| Build the final shared LED / CLI integration | `python3 rv32/led/build.py --delay 3000000` | [LED guide](led/README.md); `rv32/build/led/` |
| Rebuild the renderer-free assembly v5 checkpoint | `python3 rv32/asm_v5/build.py` | [v5 checkpoint](asm_v5/README.md); `rv32/build/asm-v5/` |
| Inspect the complete distance-11 target test | Read the archived summary first | [Summary](../measurements/stage4-asm-v5-distance11/20261006T114648Z-RV32_ISS-0d1d38/summary.json), [reproduction](distance11/README.md) |
| Inspect visual-pipeline operation and controls | Follow the recorded Clock steps | [Pipeline walkthrough](led/supplementary/windows-pipeline/20261007/WALKTHROUGH.md) |
| Build the GCC-generated reference | `python3 rv32/build_baseline.py` | Instructions below; `rv32/build/gcc/` |

Builds require Python 3 and the GNU `riscv64-unknown-elf-` tools on PATH.
Formal measurements use Windows Ripes `v2.2.6-106-g5b8a616`, `RV32_ISS`,
RV32I only, with rendering compiled out. Completion checks require
x25=`0x600d`, x26=`0`, and the expected length in x27.

## Checkpoints and current status

| Checkpoint | Runtime change / purpose | Evidence |
| --- | --- | --- |
| [GCC reference](#gcc-reference-build-and-measurement) | C v2 compiled with `-O2 -march=rv32i -mabi=ilp32` | [GCC runs](../measurements/stage4-gcc/) |
| [Assembly v1](asm_v1/README.md) | Initial hand-written parser, search and replay | [v1 runs](../measurements/stage4-asm-v1/) |
| [Assembly v2](asm_v2/README.md) | Remove a redundant depth check | [v2 runs](../measurements/stage4-asm-v2/) |
| [Assembly v3](asm_v3/README.md) | Return early for solved roots | [v3 runs](../measurements/stage4-asm-v3/) |
| [Assembly v4](asm_v4/README.md) | Keep active search state in registers | [v4 runs](../measurements/stage4-asm-v4/) |
| [Assembly v5](asm_v5/README.md) | Reduce parser overhead | [v5 runs](../measurements/stage4-asm-v5/) |
| [Full distance-11 gate](distance11/README.md) | Validate the unchanged v5 runtime on all 2,644 hardest states | [Complete archive](../measurements/stage4-asm-v5-distance11/20261006T114648Z-RV32_ISS-0d1d38/) |
| [LED / CLI integration](led/README.md) | Animate the actual solution with a renderer switch | [Windows CLI](led/supplementary/windows-cli/20261007-160248/), [GUI](led/supplementary/windows-gui/WINDOWS_GUI.md), [pipeline](led/supplementary/windows-pipeline/20261007/WALKTHROUGH.md) |

Assembly v5's complete distance-11 archive reports 2,644/2,644 PASS, a maximum
of 4,391,914 retired instructions, 1,428 `.text` bytes and 126,488 static-data
bytes including the stack reservation. The required vector uses 1,468,209
retired instructions. Newly built renderer-free LED-integration ELFs retain
the solved/short/required-vector counts of 557 / 753 / 1,468,209.

Windows LED GUI observations and the three-case `RV32_5S` reproduction checks
are complete. The instruction walkthrough covers a startup store, jump flush
and register writeback. Their scope is separate from the full distance-11
`RV32_ISS` test; additional supplied inputs still need their own target checks.

### Reading historical guides

The v1–v5 README files and the full-gate guide preserve the wording used at
their checkpoints, including tasks described as pending then. Their current
completion status is recorded above and in the [measurement index](../measurements/README.md).
The full-gate source manifest includes these historical files, including the
v5 README; its prepared-build manifest also fingerprints the full-gate guide.
Changing them can invalidate a build or an existing run's resume checks.
The historical source, scripts and evidence are retained byte for byte.

## GCC reference build and measurement

This reference builds the v2 C solver without the hand-written runtime or
renderer. Its recorded Ripes results are under [stage4-gcc](../measurements/stage4-gcc/).
The instructions below reproduce that reference, not the final LED program.

From the repository root, run:

```sh
python3 rv32/build_baseline.py
```

The default cases are solved (`12345671111111`, length 0), one move
(`25314672313211`, length 1), and the required distance-11 vector
(`21345671111111`, length 11). Each case produces its own ELF in
`rv32/build/gcc/`, plus a map, disassembly, section report, symbol list and
audit JSON. `provenance.json` records the compiler, flags, environment,
source hashes and Git state. Generated build files are ignored by Git;
new measurement evidence is archived after successful Ripes execution.

For an additional input, use:

```sh
python3 rv32/build_baseline.py --state 41532672313211
```

An optional `--expected N` adds a known optimal-length check. It defaults to
-1 for arbitrary inputs. Inputs and expected lengths are defined in a separate
assembly object; there is no LTO or precomputed solution path. The target parses
the input, searches, replays every move through the verified transition tables,
and checks that replay reaches the goal. The three standard cases also check
the expected optimal length.

## Reference configuration

- Required optimization/ISA/ABI: `-O2 -march=rv32i -mabi=ilp32`.
- `-ffreestanding` selects the bare target environment. Separate function/data
  sections and linker garbage collection discard unused v1 code and tables.
- No search statistics, renderer, libc, libgcc, LTO, or target-side table build.
- The linked `.text` byte count includes startup and all live C routines.
- `--iret` measurements include startup, parsing, search, replay,
  expected-length validation and the exit environment call.
- `.rodata + .data + .bss` must fit 131,072 bytes. A fixed 4,096-byte stack is
  explicitly reserved inside `.bss` and INCLUDED in this budget; it is not a
  claim that all 4,096 bytes are used. GCC `.su` files describe individual
  function stack frames, not the total dynamic high-water mark.
- The audit also counts any other allocated non-executable ELF sections and
  checks every linked instruction against the RV32I opcode set. A static
  instruction audit alone is not a proof of runtime correctness or a retired
  instruction measurement.

## Ripes execution convention

From WSL, after building, run:

```sh
python3 rv32/run_ripes.py
```

The runner uses `C:\Tools\Ripes\Ripes.exe`, makes a unique working directory
under `C:\Tools\Ripes\hw1_stage4`, and checks target completion, replay status
and known lengths. Raw JSON reports, compiler evidence, executable hashes,
Ripes executable hash and a summary CSV are saved under
`measurements/stage4-gcc/<UTC timestamp>-<processor>-<suffix>/`. A failed run
keeps its evidence and is marked incomplete. Only the generated working copies
are placed outside the repository; the report evidence remains inside it.
To repeat the same cases on the visual pipeline model from CLI, use
`python3 rv32/run_ripes.py --processor RV32_5S`. This tests the processor;
the visual instruction walkthrough still needs separate GUI evidence.

Use the pinned Ripes `v2.2.6-106-g5b8a616`, `RV32_ISS`, source type `elf`, no
ISA extensions. This build supports `-t elf`. An example command is:

```text
Ripes.exe --mode cli --src solved.elf -t elf --proc RV32_ISS --iret --regs --runinfo --exectime --json --output solved.json
```

At exit, inspect the register report:

| Register | Meaning | Passing value |
| --- | --- | --- |
| x25 / s9 | Program reached the completion marker | 24589 (`0x600d`) |
| x26 / s10 | Validation status | 0 |
| x27 / s11 | Returned solution length | 0, 1 or 11 for the standard cases |

Status 1 means invalid input; 2 means search failed or returned an invalid
length; 3 means replay failed; 4 means the known-length check failed. Check
both completion and status: Ripes exiting normally alone is insufficient.
The renderer is absent from the GCC reference. Use the entry points above for
the hand-written runtime, LED integration and their separately recorded results.
