# Stage 4: Initial Hand-Written RV32I Design

Date: 2026-10-05

Status: design specification, before the first hand-written implementation. Register allocation and data layout below are proposed implementation decisions, not measured improvements. No assembly performance result is claimed here.

## 1. Starting point and comparison contract

The selected algorithm is the existing v2 coordinate-based iterative IDA* solver. It uses the maximum of the permutation distance and the mixed-pattern distance for input cubie labels {1, 2, 7}, with the complete orientation coordinate. It prunes consecutive turns of the same face and generates a face's three HTM siblings by advancing its quarter-turn cursors successively.

The GCC reference has already been run by the author on Windows Ripes v2.2.6-106-g5b8a616, launched from WSL, using RV32_ISS:

| Input | Expected length | Retired instructions |
| --- | ---: | ---: |
| 12345671111111 | 0 | 566 |
| 25314672313211 | 1 | 827 |
| 21345671111111 | 11 | 2,502,568 |

All three reference binaries have 1,856 bytes of linked .text and 126,476 bytes of static data including a 4,096-byte reserved stack. The archive commit is e0ee4b8260ae296df5c1a675c8a544bc17684ca0; the recorded build-time source commit is 2f575d5af1f26beb970547445c6da112891733a7.

Keep the same measurement boundary: startup and workspace initialization, input parsing, search, target replay, optional expected-length check, completion markers, and exit ecall. Rendering and search-statistics instrumentation are disabled for comparison. A hand-written search-only measurement is not comparable to this complete reference.

Keep the reference files and evidence intact. Build the hand-written variant in a separate output directory. The initial complete candidate will use hand-written runtime code for parsing, solving, replay, and the target harness. Host-generated C table objects remain permitted read-only data; verify that linking them introduces no runtime C routines or arithmetic helpers. A temporary mixed C/assembly diagnostic build, if useful, must be labeled as such and must not be presented as the final hand-written program.

## 2. Runtime boundaries

Reuse the existing startup and linker conventions. The target harness performs:

1. Parse the assembly-time input string into p and o.
2. Run the solver and store result_length and result_path.
3. Check that the returned length is in 0..11.
4. Replay the returned path from the original input coordinates.
5. Compare the length with expected_length when expected_length is nonnegative.
6. Return status to the common startup, which sets the existing completion registers and exits.

The completion protocol remains x25 = 0x600d, x26 = status, and x27 = result_length. The solver may temporarily use s9 through s11 because it restores them before returning; startup sets the completion values only after target_main returns.

Proposed assembly interfaces avoid the ABI details of passing a small C structure by value:

| Routine | Arguments | Return |
| --- | --- | --- |
| asm_parse | a0 = input pointer; a1 = pointer to two uint16 fields p, o | a0 = 1 valid, 0 invalid |
| asm_solve | a0 = unsigned p; a1 = unsigned o; a2 = path buffer of at least 11 bytes | a0 = solution length 0..11, or -1 |
| asm_replay | a0 = unsigned p; a1 = unsigned o; a2 = path pointer; a3 = length | a0 = 1 solved, 0 invalid or unsolved |
| target_main | no arguments | a0 = status: 0 success, 1 parse failure, 2 bad length/search failure, 3 replay failure, 4 expected-length mismatch |

Do not treat asm_solve as a drop-in ABI replacement for v2_solve(v1_coord, path); the argument layouts differ. The assembly harness calls the explicit scalar interface.

Follow the standard integer calling convention: preserve any s0..s11 used, preserve sp, leave gp and tp alone, and keep sp aligned to 16 bytes. asm_solve is planned as a leaf routine, with heuristic lookup expanded inside the routine rather than called for every child. Saving twelve s registers needs a 48-byte stack frame, already a multiple of 16. A leaf that never changes ra does not need to save ra. Other routines get their own documented frames; determine the complete maximum call-stack use from the implemented call graph.

## 3. Search-frame layout

Keep the existing compact 12-byte frame layout for the first implementation:

| Byte offset | Field | Width | Meaning |
| ---: | --- | ---: | --- |
| 0 | p | 2 | State at this depth, before choosing the next move |
| 2 | o | 2 | State orientation at this depth |
| 4 | cursor_p | 2 | Permutation cursor for this face's successive siblings |
| 6 | cursor_o | 2 | Orientation cursor for the same siblings |
| 8 | face | 1 | Current face, 0..2; 3 means exhausted |
| 9 | turn | 1 | Next sibling ordinal, 0..2; 3 means this face is exhausted |
| 10 | previous_face | 1 | Face used to enter this node; root uses sentinel 3 |
| 11 | padding | 1 | Unused |

Reserve twelve frames, 144 bytes, with at least four-byte alignment. Use lhu/sh for coordinates and lbu/sb for control bytes. Coordinates are unsigned; signed halfword loads are inappropriate as a general convention even though the current coordinate values are small.

Keep a frame pointer. Descending increments it by 12; backtracking decrements it by 12. There is no need to compute depth * 12 inside the loop. The architectural call stack and this explicit search-frame array serve different purposes: the former preserves function context, while the latter preserves DFS continuation state. The search is not recursive.

For the initial implementation, update the cursor and turn in the parent frame before pruning or descending. Reload frame fields as needed. Holding more active-frame fields in registers and spilling only on descent is a later experiment, after a working measured version exists.

## 4. Planned solver register allocation

| Register | Role |
| --- | --- |
| s0 | Current search-frame pointer |
| s1 | Base of the output path buffer |
| s2 | Current depth |
| s3 | Current IDA* threshold (bound) |
| s4 | Permutation transition row for the current face |
| s5 | Orientation transition row for the current face |
| s6 | Base of v1_perm_dist |
| s7 | Base of v2_projection |
| s8 | Base of v2_row_offset |
| s9 | Base of v2_packed |
| s10 | Starting permutation coordinate |
| s11 | Starting orientation coordinate |
| a0..a7, t0..t6 | Temporary fields, child coordinates, addresses, distances, remaining depth, and comparisons |
| sp | ABI stack only |
| ra | Caller return address; unchanged inside the leaf solver |

The allocation deliberately keeps the input coordinates for restarting each IDA* threshold and reserves two registers for the selected transition rows. It does not assume caller-saved registers survive function calls. If a helper call is introduced later, audit every live value across that call and revise the save/restore plan.

## 5. Table addressing

Reuse all six live v2 tables without regenerating their contents. Their payload is 122,184 bytes:

| Table | Bytes | Access |
| --- | ---: | --- |
| v1_perm_next[3][5040] | 30,240 | unsigned halfword |
| v1_ori_next[3][729] | 4,374 | unsigned halfword |
| v1_perm_dist[5040] | 5,040 | unsigned byte |
| v2_projection[5040] | 5,040 | unsigned byte |
| v2_row_offset[210] | 840 | 32-bit word |
| v2_packed[210 * 365] | 76,650 | unsigned byte, then nibble extraction |

Permutation row stride is 10,080 bytes; orientation row stride is 1,458 bytes. To avoid rebuilding these offsets for every candidate, add a small read-only descriptor with three entries, each containing two linked 32-bit addresses:

| Entry | Permutation address | Orientation address |
| --- | --- | --- |
| R / face 0 | v1_perm_next + 0 | v1_ori_next + 0 |
| B / face 1 | v1_perm_next + 10080 | v1_ori_next + 1458 |
| D / face 2 | v1_perm_next + 20160 | v1_ori_next + 2916 |

This costs 24 bytes plus any alignment. Indexing an entry uses face << 3. Load s4 and s5 when selecting a valid face, entering a child, or restoring a parent. Do not index the descriptor when face == 3. This caches row addresses only; it does not add a new state-transition table or change the search.

A cursor transition then has the form:

    next_p = load_u16(s4 + (cursor_p << 1))
    next_o = load_u16(s5 + (cursor_o << 1))

For the heuristic, test the permutation bound first. Only if it passes, compute:

    q      = load_u8(projection + next_p)
    row    = load_u32(row_offset + (q << 2))
    byte   = load_u8(packed + row + (next_o >> 1))
    shift  = (next_o & 1) << 2
    mixed  = (byte >> shift) & 15

row_offset entries are uint32_t, not uint16_t: the last row starts at 209 * 365 = 76,285, beyond the unsigned 16-bit range. The maximum packed-byte offset is 76,285 + (728 >> 1) = 76,649, within the 76,650-byte array.

The 365-byte row stride includes padding for the odd 729-entry row. Use the verified row offsets and per-row nibble parity. Replacing this with a flat (q * 729 + o) / 2 calculation would change the layout and give incorrect accesses.

All run-time address arithmetic uses RV32I shifts and additions. Link-time constant expressions in the descriptor do not execute multiplication on the target.

## 6. Control flow and invariants

Keep the C version's threshold sequence and move order. Compute the initial max heuristic, handle the solved root, and iterate thresholds up to 11. On each threshold, initialize the root frame with p/o, matching cursors, face = turn = 0, and previous_face = 3.

At each frame:

1. If face == 3, backtrack. Exhausting the root finishes this threshold.
2. If face equals previous_face, or turn == 3, advance face, clear turn, and reset both cursors to the frame's p/o. Select new transition rows only if face remains below 3.
3. Advance both cursors once through the current face's quarter-turn tables. Form move = 3 * face + old_turn using shifts/additions. Increment and save turn before any descent. Save the updated cursors even if this candidate is rejected.
4. Set child_depth = depth + 1. Retain the initial implementation's explicit depth-bound check. Compute remaining = bound - child_depth only when that subtraction is valid.
5. Reject if permutation_distance > remaining. Otherwise load and unpack the mixed distance, and reject if it exceeds remaining.
6. Store path[depth] = move. If both child coordinates are zero, return child_depth.
7. If child_depth < bound, descend: initialize the next frame with the child state, cursor copies, face = turn = 0, and previous_face equal to the parent's face. Select face-0 rows for the child.
8. Otherwise remain at the same frame and try its next candidate.

On backtracking, reload the parent's face and reselect its transition rows before generating another sibling. A child's cached rows must not be reused for its parent.

Key invariants:

- Frame p/o never change while enumerating its children; its cursors do change.
- R, R2, R' are siblings at depth + 1, even though successive table advances generate them.
- A pruned R candidate does not reset the cursor before generating R2.
- A parent's turn points past the explored candidate before control enters its child.
- Only path[0..returned_length) is an answer; stale bytes after that prefix are irrelevant.
- Both p and o must be zero for success.
- A leaf at the threshold does not create another search frame.

Optimality uses the existing admissibility argument: neither abstract distance exceeds the true remaining solution length, so their maximum cannot prune a shortest path at its exact threshold. Consecutive same-face moves cannot be necessary in an HTM-shortest path. Increasing thresholds one at a time from the admissible lower bound therefore finds a shortest solution. Assembly translation still needs its own correctness testing; the C proof does not certify its implementation.

## 7. Parsing, replay, and future rendering

The first parser preserves the C input contract: seven distinct digits '1'..'7', followed by seven digits '1'..'3', a terminating NUL at position 14, and an orientation sum divisible by three. Reject at the first invalid character, including an early NUL. Use a seven-bit seen mask for the permutation and a seven-byte temporary permutation buffer.

Compute the permutation rank using the existing smaller-after counts and fixed mixed-radix multipliers 6, 5, 4, 3, 2, expressed with shifts/additions. Compute the orientation coordinate from the first six orientation digits as o = 3 * o + digit. Validate all seven orientation digits and reduce their total sum by repeated subtraction of three. Avoid introducing a general multiply/divide helper.

Replay receives the original start coordinates and the returned path. Reject move IDs >= 9. Decode face and the number of quarter turns using the existing ranges 0..2, 3..5, 6..8 rather than division and remainder by three. Verify that the final p/o are both zero. This target replay uses the previously verified transition tables; the host cubie-level oracle remains the independent physical model.

The solver returns move IDs in the existing order R, R2, R', B, B2, B', D, D2, D'. This stable interface supports later LED rendering. Rendering can show the initial cube and then apply the actual returned moves in order after the search completes. It must not animate rejected search branches or a prerecorded answer. Keep rendering outside the search loop and behind an assembly-time switch, so the same core serves both builds. GUI peripheral-symbol integration will be handled in the rendering stage.

## 8. Resource budget and first implementation gate

The row descriptor increases the table-related payload from 122,184 to 122,208 bytes. The 128 KiB budget then leaves 8,864 bytes for workspace, the reserved stack, input/output, other constants, and padding. Preserve the initial 4,096-byte stack reservation for now. Count the 144-byte search array, 11-byte path, result length, input, expected length, and all linked alignment. The exact final total must come from the ELF audit, not this payload calculation. Also document actual maximum stack use separately from the reservation.

The first implementation is complete only after:

- Assembly and link succeed for RV32I/ILP32, with no forbidden opcodes, unresolved symbols, or arithmetic helpers.
- Linked static data including the reserved stack satisfy 131,072 bytes.
- Solved, short, and specified distance-11 cases pass target replay and known-length checks on the pinned Ripes ISS.
- An additional valid non-fixture state is supported; malformed-input behavior and even/odd packed accesses receive targeted checks during implementation.
- .text and --iret are recorded using the same boundary as the GCC reference.
- Sources, input values, flags, fingerprints, Ripes version, and raw reports are archived.

These initial checks are not the final all-2,644 distance-11 performance gate or visual-pipeline validation. Do not claim either from three cases. Host emulator checks, if used to debug the assembly, supplement rather than replace Ripes evidence.

## 9. Refinement after the first measurement

The first version already makes deliberate assembly choices: explicit scalar interfaces, fixed pattern data, register-held table bases, cached transition rows, frame-pointer movement, and a leaf search loop. It is not intended to be a deliberately poor baseline.

After measuring and saving it, inspect the actual hot path. Candidate experiments include keeping active cursor/control fields in registers and spilling only on descent, removing branches justified by established loop invariants, and comparing shared helper code against duplicated lookup sequences for code-size/instruction-count trade-offs. Each retained change gets a concrete hypothesis, correctness checks, and actual .text/iret measurements. Do not report these candidates as implemented improvements or invent intermediate results.

Commit the first working hand-written version together with its measurements. A separate planning-only commit is optional, not required to manufacture development history. Update HackMD when this produces a measured result; the AI Usage Disclosure wording remains a separate pending discussion.

## References and provenance

- Existing v2 source inspected locally: optimized_v2/v2.c, optimized_v2/v2.h, optimized/v1.c, optimized/v1.h in the archived 2f575d5 source tree.
- Existing GCC harness: rv32/start.S, rv32/link.ld, rv32/target_main.c, rv32/build_baseline.py. Its eight package files match the previously delivered baseline ZIP byte for byte; C source hashes match the saved build provenance.
- GCC evidence: https://github.com/Evan-1212/minirubik/tree/e0ee4b8260ae296df5c1a675c8a544bc17684ca0/measurements/stage4-gcc/20261005T080153Z-RV32_ISS-ea1f92
- Assignment constraints: retained homework-page snapshot. The live page could not be fetched during this design review: https://hackmd.io/@sysprog/2026-arch-homework1
- RISC-V calling convention: https://riscv-non-isa.github.io/riscv-elf-psabi-doc/
