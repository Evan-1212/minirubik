/* asm_replay(p,o,path,length): a0 = 1 if replay ends solved, else 0.
 * Leaf; no stack allocation. Same verified quarter-turn tables as C. */
    .option norvc
    .section .text.asm_replay,"ax",@progbits
    .globl asm_replay
    .type asm_replay,@function
asm_replay:
    beqz a2, .Lreplay_fail
    li t4, 11
    bltu t4, a3, .Lreplay_fail
    li t4, 5040
    bgeu a0, t4, .Lreplay_fail
    li t4, 729
    bgeu a1, t4, .Lreplay_fail
    mv t0, a0
    mv t1, a1
    mv t2, a2
    mv t3, a3
.Lreplay_move:
    beqz t3, .Lreplay_goal
    lbu t4, 0(t2)
    addi t2, t2, 1
    li t5, 9
    bgeu t4, t5, .Lreplay_fail
    li t5, 3
    bltu t4, t5, .Lreplay_r
    li t5, 6
    bltu t4, t5, .Lreplay_b
    li t6, 2
    addi t5, t4, -5
    j .Lreplay_rows
.Lreplay_b:
    li t6, 1
    addi t5, t4, -2
    j .Lreplay_rows
.Lreplay_r:
    li t6, 0
    addi t5, t4, 1
.Lreplay_rows:
    la a6, asm_face_rows
    slli t6, t6, 3
    add a6, a6, t6
    lw a4, 0(a6)
    lw a5, 4(a6)
.Lreplay_quarter:
    slli a6, t0, 1
    add a6, a4, a6
    lhu t0, 0(a6)
    slli a6, t1, 1
    add a6, a5, a6
    lhu t1, 0(a6)
    addi t5, t5, -1
    bnez t5, .Lreplay_quarter
    addi t3, t3, -1
    j .Lreplay_move
.Lreplay_goal:
    or a0, t0, t1
    seqz a0, a0
    ret
.Lreplay_fail:
    li a0, 0
    ret
    .size asm_replay, .-asm_replay
