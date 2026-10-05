/* asm_parse(input, out): out = two uint16_t fields; a0 = 1/0.
 * Leaf; 16-byte local frame: permutation[7], padding, inversion_counts[6]. */
    .option norvc
    .section .text.asm_parse,"ax",@progbits
    .globl asm_parse
    .type asm_parse,@function
asm_parse:
    addi sp, sp, -16
    beqz a0, .Lparse_fail
    beqz a1, .Lparse_fail
    li t0, 0
    li t1, 0
.Lparse_perm:
    add t4, a0, t0
    lbu t2, 0(t4)
    addi t2, t2, -49
    li t5, 7
    bgeu t2, t5, .Lparse_fail
    li t3, 1
    sll t3, t3, t2
    and t6, t1, t3
    bnez t6, .Lparse_fail
    or t1, t1, t3
    add t4, sp, t0
    sb t2, 0(t4)
    addi t0, t0, 1
    bltu t0, t5, .Lparse_perm

    li t0, 0
    li t1, 0                  /* orientation sum */
    li t2, 0                  /* orientation rank */
.Lparse_ori:
    add t4, a0, t0
    lbu t3, 7(t4)
    addi t3, t3, -49
    li t5, 3
    bgeu t3, t5, .Lparse_fail
    add t1, t1, t3
    li t5, 6
    bgeu t0, t5, .Lparse_ori_next
    slli t6, t2, 1
    add t2, t2, t6
    add t2, t2, t3
.Lparse_ori_next:
    addi t0, t0, 1
    li t5, 7
    bltu t0, t5, .Lparse_ori
    lbu t3, 14(a0)
    bnez t3, .Lparse_fail
    li t5, 3
.Lparse_reduce:
    bltu t1, t5, .Lparse_sum_done
    addi t1, t1, -3
    j .Lparse_reduce
.Lparse_sum_done:
    bnez t1, .Lparse_fail
    mv a2, t2                 /* preserve o while calculating p */

    li t0, 0                  /* i */
.Lparse_count_outer:
    add t5, sp, t0
    lbu t3, 0(t5)             /* p[i] */
    li t1, 0                  /* smaller_after count */
    addi t2, t0, 1            /* j */
    li t6, 7
.Lparse_count_inner:
    add t5, sp, t2
    lbu t4, 0(t5)
    sltu t4, t4, t3
    add t1, t1, t4
    addi t2, t2, 1
    bltu t2, t6, .Lparse_count_inner
    add t5, sp, t0
    sb t1, 8(t5)
    addi t0, t0, 1
    li t6, 6
    bltu t0, t6, .Lparse_count_outer

    lbu t0, 8(sp)
    slli t1, t0, 2
    slli t0, t0, 1
    add t0, t0, t1            /* x6 */
    lbu t1, 9(sp)
    add t0, t0, t1
    slli t1, t0, 2
    add t0, t0, t1            /* x5 */
    lbu t1, 10(sp)
    add t0, t0, t1
    slli t0, t0, 2            /* x4 */
    lbu t1, 11(sp)
    add t0, t0, t1
    slli t1, t0, 1
    add t0, t0, t1            /* x3 */
    lbu t1, 12(sp)
    add t0, t0, t1
    slli t0, t0, 1            /* x2 */
    lbu t1, 13(sp)
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
