# Stage 4: GCC RV32I reference, first checkpoint

This checkpoint builds the existing v2 C solver. It does not yet contain the
hand-written solver or claim Ripes performance results. The C search and its
host-generated tables are unchanged.

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
measurement evidence will be archived after successful Ripes execution.

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
- Future `--iret` measurements include startup, parsing, search, replay,
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
The renderer is absent at this checkpoint. GUI rendering and the hand-written
solver will be added in later, separately measured checkpoints.
