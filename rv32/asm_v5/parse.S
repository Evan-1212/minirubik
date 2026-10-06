/* asm_parse(input, out): out = two uint16_t fields; a0 = 1/0.
 * Leaf; 16-byte local frame containing six inversion counts.
 * Validate and reread the original permutation bytes instead of copying them.
 * Pointer loops and invariant constants reduce per-character overhead. */
    .option norvc
    .section .text.asm_parse,"ax",@progbits
    .globl asm_parse
    .type asm_parse,@function
asm_parse:
    addi sp, sp, -16
    beqz a0, .Lparse_fail
    beqz a1, .Lparse_fail
    li a3, 7
    li a4, 1
    li a5, 3
    addi a6, a0, 7
    mv t0, a0
    li t1, 0                 /* permutation digit bitset */
.Lparse_perm:
    lbu t2, 0(t0)
    addi t2, t2, -49
    bgeu t2, a3, .Lparse_fail
    sll t3, a4, t2
    and t6, t1, t3
    bnez t6, .Lparse_fail
    or t1, t1, t3
    addi t0, t0, 1
    bne t0, a6, .Lparse_perm

    /* First six trits form o; the seventh participates only in the sum. */
    addi a6, a0, 13
    li t1, 0
    li t2, 0
.Lparse_ori:
    lbu t3, 0(t0)
    addi t3, t3, -49
    bgeu t3, a5, .Lparse_fail
    add t1, t1, t3
    slli t6, t2, 1
    add t2, t2, t6
    add t2, t2, t3
    addi t0, t0, 1
    bne t0, a6, .Lparse_ori
    lbu t3, 13(a0)
    addi t3, t3, -49
    bgeu t3, a5, .Lparse_fail
    add t1, t1, t3
    lbu t3, 14(a0)
    bnez t3, .Lparse_fail
.Lparse_reduce:
    bltu t1, a5, .Lparse_sum_done
    addi t1, t1, -3
    j .Lparse_reduce
.Lparse_sum_done:
    bnez t1, .Lparse_fail
    mv a2, t2                 /* preserve o while calculating p */

    /* ASCII digits have the same order as the validated values 0..6.
     * All input reads precede output stores. Keep the original inversion
     * counts and mixed-radix calculation; only traversal/storage changes. */
    mv t0, a0
    addi a3, a0, 6
    mv a4, sp
    addi a6, a0, 7
.Lparse_count_outer:
    lbu t3, 0(t0)
    li t1, 0
    addi t5, t0, 1
.Lparse_count_inner:
    lbu t4, 0(t5)
    sltu t4, t4, t3
    add t1, t1, t4
    addi t5, t5, 1
    bne t5, a6, .Lparse_count_inner
    sb t1, 0(a4)
    addi a4, a4, 1
    addi t0, t0, 1
    bne t0, a3, .Lparse_count_outer

    lbu t0, 0(sp)
    slli t1, t0, 2
    slli t0, t0, 1
    add t0, t0, t1            /* x6 */
    lbu t1, 1(sp)
    add t0, t0, t1
    slli t1, t0, 2
    add t0, t0, t1            /* x5 */
    lbu t1, 2(sp)
    add t0, t0, t1
    slli t0, t0, 2            /* x4 */
    lbu t1, 3(sp)
    add t0, t0, t1
    slli t1, t0, 1
    add t0, t0, t1            /* x3 */
    lbu t1, 4(sp)
    add t0, t0, t1
    slli t0, t0, 1            /* x2 */
    lbu t1, 5(sp)
    add t0, t0, t1
    sh t0, 0(a1)
    sh a2, 2(a1)
    li a0, 1
    j .Lparse_return
.Lparse_fail:
    li a0, 0
.Lparse_return:
    addi sp, sp, 16
    ret
    .size asm_parse, .-asm_parse
