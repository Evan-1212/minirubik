# Full distance-11 target gate for assembly v5

This is a validation stage, not an assembly v6. The runtime is unchanged:
v5 parser, v4 solver, v1 replay/target, and the common startup and tables.
The base archive commit is `de9e008c02db76f6dd1ee63f39ff035af9e6b495`.

## Run in WSL

From `/home/evan/projects/minirubik`, with the same GCC 13.2/binutils 2.42
toolchain and Windows Ripes installation used for the v5 smoke run:

```sh
python3 rv32/distance11/prepare.py
python3 rv32/distance11/run.py
```

The second command runs all remaining cases sequentially. Keep the computer
awake while it runs. Progress appears for the first three new cases and then
every 25 completed cases, with an estimate based on observed elapsed time.
The estimate includes compilation and process-launch overhead and is not a
simulated-program performance result.

To stop at a clean checkpoint after a bounded batch, use:

```sh
python3 rv32/distance11/run.py --max-new 25
```

The same command without `--max-new` resumes and finishes the remaining cases.
Ctrl+C also preserves completed cases. An interrupted Ripes invocation may
remain alive until its timeout (about two minutes); allow it to finish before
resuming. Its output has a unique attempt name and cannot be mistaken for a
later attempt. Do not run two copies of the runner simultaneously.

```sh
python3 rv32/distance11/run.py
python3 rv32/distance11/run.py --verify-only
```

The active archive is remembered under `rv32/build/distance11/active-run.json`.
Use `--resume measurements/stage4-asm-v5-distance11/<run-id>` to select an
existing run explicitly, or `--new-run` only when a separate full remeasurement
is intended. Neither option deletes earlier evidence. A complete valid archive
is checked and reported without launching Ripes again.

## Coverage and executable identity

The case list comes from the already archived host result
`measurements/2026-10-05-stage3/v2-distance11.csv`. Preparation checks exactly
2,644 unique sorted ranks, valid input encodings and expected length 11. A
host-only BFS using the existing independent cubie moves verifies that this
is exactly the full distance-11 shell. This short coverage check does not rerun
the previous exhaustive C-solver validation. Host BFS data are never linked
into the target.

Preparation compiles the unchanged common runtime once into a separate build
directory. Its template ELF for `21345671111111` must match the archived v5
ELF SHA-256 byte for byte. The template receives the existing full ISA and
memory audit: linked `.text` 1,428 bytes; static data including the reserved
4,096-byte stack 126,488 bytes, below 131,072.

For each case, the runner assembles a new 14-character input with expected
length 11 and links it with those common objects. It checks the entire linked
ELF against the audited template, allowing differences only in the 15-byte
`cube_input` string including NUL. The runner does **not** patch the executable
it measures; the byte substitution is only an independent equality check.
Thus code, tables, ABI flags, addresses, stack reservation and measurement
boundary are identical for every case. Object/source hashes and compiler
versions are checked on resume.

## Target pass conditions

Each invocation uses the pinned Windows Ripes
`v2.2.6-106-g5b8a616`, SHA-256
`bd2ddea8cd6fcf6902cda7366fe99ab6dd0c7fdbbc7efcfdb89ede20acc67f0f`,
at `C:\Tools\Ripes\Ripes.exe`. The runner uses `RV32_ISS` without extensions
and rendering is compiled out. It checks:

- Ripes exits successfully and produces a fresh, matching JSON report.
- `runinfo` identifies `RV32_ISS`, no ISA extensions and the correct source ELF.
- Completion marker `x25 = 0x600d`, target status `x26 = 0`, solution length
  `x27 = 11`, and exit ecall number `x17 = 10`.
- Retired instructions are positive and at most **50,000,000 per state**.

Target status zero means the existing harness passed parsing, solving,
coordinate replay and expected-length verification. The input's independently
established exact distance is 11, so that length is optimal. Counts include
startup, parsing, solving, replay, the length check and exit ecall, as in the
previous smoke measurements. Simulator wall time is not a performance metric.

Only a complete set of 2,644 passing results prints:

```text
ASM_V5_DISTANCE11_GATE=PASS
```

A partial batch prints `INCOMPLETE`. A launch error, timeout, incorrect result
or over-budget case stops the run and retains its attempt evidence. Resume
checks every saved success against its raw report and input/ELF identity before
skipping it. A missing or corrupt success record is not silently accepted.
Failed attempts have no passing result record and are retried with new names.

## Evidence and scope

New files are written under:

- `rv32/build/distance11/`: ignored common objects and temporary link products.
- `measurements/stage4-asm-v5-distance11/<run-id>/`: official local evidence.
- `C:\Tools\Ripes\hw1_stage4_distance11\<run-id>\`: Windows launch workspace.

The evidence archive contains one audited template ELF and shared build
records, `ripes-environment.json`, the full case list, raw per-attempt Ripes
JSON, commands, input assembly, launch logs, per-case success records, and
`summary.csv`/`summary.json`. Summaries report coverage, minimum, mean and
maximum retired instructions, and the worst input. Identical tables and
disassemblies are retained once rather than repeated 2,644 times. Per-state
ELFs can be reproduced from the archived build recipe and input; their hashes
are recorded. Resume uses the matching prepared build directory, so preserve it
until the run is complete. No automatic Git commit or push is performed.

Development-environment tests in `testing/` exercise report rejection,
tampering detection and checkpoint handling. They are not Ripes measurements.
The full target gate must run on the user's pinned installation. Visual
pipeline validation, LED rendering and final repository cleanup remain separate
later tasks.
