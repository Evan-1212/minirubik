/* RENDER=0 preserves the asm-v5 measurement/validation contract as rv32/target_main.c.
 * Frame 32 B: start.p/o at 0/2; ra at 28. Maximum total stack: 80 B.
 * target_main (32) -> asm_solve (48); parser uses 16, replay uses 0. */
    .option norvc
    .section .bss.result,"aw",@nobits
    .balign 4
    .globl result_length
    .type result_length,@object
result_length:
    .zero 4
    .size result_length, .-result_length
    .globl result_path
    .type result_path,@object
result_path:
    .zero 11
    .size result_path, .-result_path

    .section .rodata.asm_face_rows,"a",@progbits
    .balign 4
    .globl asm_face_rows
    .type asm_face_rows,@object
asm_face_rows:
    .word v1_perm_next,         v1_ori_next
    .word v1_perm_next + 10080, v1_ori_next + 1458
    .word v1_perm_next + 20160, v1_ori_next + 2916
    .size asm_face_rows, .-asm_face_rows

    .section .text.target_main,"ax",@progbits
    .globl target_main
    .type target_main,@function
 target_main:
    addi sp, sp, -32
    sw ra, 28(sp)
    la t0, result_length
    li t1, -1
    sw t1, 0(t0)
    la a0, cube_input
    mv a1, sp
    call asm_parse
    beqz a0, .Ltarget_parse_failure
    .if RENDER
    la a0, cube_input
    call led_begin
    beqz a0, .Ltarget_renderer_failure
    .endif
    lhu a0, 0(sp)
    lhu a1, 2(sp)
    la a2, result_path
    call asm_solve
    la t0, result_length
    sw a0, 0(t0)
    li t1, 11
    bltu t1, a0, .Ltarget_solve_failure
    mv a3, a0
    lhu a0, 0(sp)
    lhu a1, 2(sp)
    la a2, result_path
    call asm_replay
    beqz a0, .Ltarget_replay_failure
    la t0, expected_length
    lw t1, 0(t0)
    bltz t1, .Ltarget_success
    la t0, result_length
    lw t0, 0(t0)
    bne t0, t1, .Ltarget_length_failure
.Ltarget_success:
    .if RENDER
    la a0, result_path
    la t0, result_length
    lw a1, 0(t0)
    call led_animate
    .endif
    li a0, 0
    j .Ltarget_return
.Ltarget_parse_failure:
    li a0, 1
    j .Ltarget_return
.Ltarget_solve_failure:
    li a0, 2
    j .Ltarget_return
.Ltarget_replay_failure:
    li a0, 3
    j .Ltarget_return
.Ltarget_length_failure:
    li a0, 4
    .if RENDER
    j .Ltarget_return
.Ltarget_renderer_failure:
    li a0, 5
    .endif
.Ltarget_return:
    lw ra, 28(sp)
    addi sp, sp, 32
    ret
    .size target_main, .-target_main
