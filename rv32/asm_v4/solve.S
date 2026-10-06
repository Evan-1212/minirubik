/* asm_solve(p, o, path): scalar ABI; returns length 0..11 or -1.
 * Leaf function: 0 stack bytes for solved/invalid early returns;
 * 48-byte ABI save area for search; search uses static frames.
 * s0 frame; s1 path; s2 depth; s3 bound; s4/s5 current transition rows;
 * s6 perm_dist; s7 projection; s8 row_offset; s9 packed; s10/s11 root p/o.
 * Active continuation: t2/t3 cursor p/o; a3 face; a4 next turn; a5 prev.
 * Frame offsets: p=0,o=2,cursor_p=4,cursor_o=6,face=8,turn=9,prev=10.
 * Only p/o are authoritative in the active frame. Continuation slots are
 * written before descent and read on backtrack; they may otherwise be stale.
 * No recursion, heap, runtime table generation, or search statistics. */
    .option norvc
    .section .bss.asm_frames,"aw",@nobits
    .balign 4
    .type asm_frames,@object
asm_frames:
    .zero 144
    .size asm_frames, .-asm_frames

    .section .text.asm_solve,"ax",@progbits
    .globl asm_solve
    .type asm_solve,@function
asm_solve:
    /* Keep the argument contract, including non-null path for solved input.
     * These checks touch only caller-saved registers. */
    beqz a2, .Lsolve_invalid
    li t0, 5040
    bgeu a0, t0, .Lsolve_invalid
    li t0, 729
    bgeu a1, t0, .Lsolve_invalid
    or t0, a0, a1
    /* Both coordinates are zero, hence a0 is already the return value.
     * Jump directly to ret, skipping both the prologue and epilogue. */
    beqz t0, .Lsolve_direct_return

    addi sp, sp, -48
    sw s0, 0(sp)
    sw s1, 4(sp)
    sw s2, 8(sp)
    sw s3, 12(sp)
    sw s4, 16(sp)
    sw s5, 20(sp)
    sw s6, 24(sp)
    sw s7, 28(sp)
    sw s8, 32(sp)
    sw s9, 36(sp)
    sw s10, 40(sp)
    sw s11, 44(sp)
    mv s10, a0
    mv s11, a1
    mv s1, a2
    la s6, v1_perm_dist
    la s7, v2_projection
    la s8, v2_row_offset
    la s9, v2_packed

    /* Non-solved root: max(permutation distance, mixed distance). */
    add t0, s6, s10
    lbu s3, 0(t0)
    add t0, s7, s10
    lbu t0, 0(t0)
    slli t0, t0, 2
    add t0, s8, t0
    lw t0, 0(t0)
    srli t1, s11, 1
    add t0, t0, t1
    add t0, s9, t0
    lbu t0, 0(t0)
    andi t1, s11, 1
    slli t1, t1, 2
    srl t0, t0, t1
    andi t0, t0, 15
    bgeu s3, t0, .Lsolve_initial_bound
    mv s3, t0
.Lsolve_initial_bound:
    li t0, 12
    bgeu s3, t0, .Lsolve_fail
.Lsolve_threshold:
    la s0, asm_frames
    li s2, 0
    sh s10, 0(s0)
    sh s11, 2(s0)
    mv t2, s10
    mv t3, s11
    li a3, 0
    li a4, 0
    li a5, 3

.Lsolve_select_rows:
    li t1, 3
    beq a3, t1, .Lsolve_loop /* no descriptor entry for exhausted face */
    la t1, asm_face_rows
    slli t0, a3, 3
    add t1, t1, t0
    lw s4, 0(t1)
    lw s5, 4(t1)
.Lsolve_loop:
    li t1, 3
    beq a3, t1, .Lsolve_exhausted
    beq a3, a5, .Lsolve_next_face
    beq a4, t1, .Lsolve_next_face

    slli t0, t2, 1
    add t0, s4, t0
    lhu t2, 0(t0)             /* advance cursor even if candidate pruned */
    slli t0, t3, 1
    add t0, s5, t0
    lhu t3, 0(t0)
    slli a0, a3, 1
    add a0, a0, a3
    add a0, a0, a4            /* move = 3*face + old turn */
    addi a4, a4, 1            /* advance parent's continuation first */
    addi a1, s2, 1            /* child_depth */
    /* depth < bound at loop entry, so child_depth <= bound. */
    sub a2, s3, a1            /* remaining >= 0 */

    add t4, s6, t2
    lbu t4, 0(t4)
    bltu a2, t4, .Lsolve_loop
    add t4, s7, t2
    lbu t4, 0(t4)
    slli t4, t4, 2
    add t4, s8, t4
    lw t4, 0(t4)             /* uint32 row offset, can exceed 65535 */
    srli t5, t3, 1
    add t4, t4, t5
    add t4, s9, t4
    lbu t4, 0(t4)
    andi t5, t3, 1
    slli t5, t5, 2
    srl t4, t4, t5
    andi t4, t4, 15
    bltu a2, t4, .Lsolve_loop

    add t4, s1, s2
    sb a0, 0(t4)
    or t4, t2, t3
    beqz t4, .Lsolve_found
    bgeu a1, s3, .Lsolve_loop
    /* Suspend the parent's already-advanced continuation. These five
     * stores occur only on actual descent, not on every candidate. */
    sh t2, 4(s0)
    sh t3, 6(s0)
    sb a3, 8(s0)
    sb a4, 9(s0)
    sb a5, 10(s0)
    mv s2, a1
    addi s0, s0, 12
    sh t2, 0(s0)
    sh t3, 2(s0)
    mv a5, a3                /* child's previous face is parent's face */
    li a3, 0
    li a4, 0
    j .Lsolve_select_rows

.Lsolve_next_face:
    addi a3, a3, 1
    li a4, 0
    lhu t2, 0(s0)
    lhu t3, 2(s0)
    j .Lsolve_select_rows
.Lsolve_exhausted:
    beqz s2, .Lsolve_next_threshold
    addi s2, s2, -1
    addi s0, s0, -12
    lhu t2, 4(s0)
    lhu t3, 6(s0)
    lbu a3, 8(s0)
    lbu a4, 9(s0)
    lbu a5, 10(s0)
    j .Lsolve_select_rows    /* restore parent's cached row addresses */
.Lsolve_next_threshold:
    addi s3, s3, 1
    li t0, 12
    bltu s3, t0, .Lsolve_threshold
.Lsolve_fail:
    li a0, -1
    j .Lsolve_return
.Lsolve_found:
    mv a0, a1
.Lsolve_return:
    lw s0, 0(sp)
    lw s1, 4(sp)
    lw s2, 8(sp)
    lw s3, 12(sp)
    lw s4, 16(sp)
    lw s5, 20(sp)
    lw s6, 24(sp)
    lw s7, 28(sp)
    lw s8, 32(sp)
    lw s9, 36(sp)
    lw s10, 40(sp)
    lw s11, 44(sp)
    addi sp, sp, 48
.Lsolve_direct_return:
    ret
.Lsolve_invalid:
    li a0, -1
    ret
    .size asm_solve, .-asm_solve
