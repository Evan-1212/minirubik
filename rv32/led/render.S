/* Renderer only: RENDER=0 removes code, constants, and workspace.
 * Cubie labels here are 0..7 (0 fixed FUL); twists are internal 0..2.
 * No coordinate unranking or change to the measured search is required. */
    .if RENDER
    .option norvc
    .section .bss.led,"aw",@nobits
    .balign 4
led_state:                       /* p[8], o[8], next_p[8], next_o[8] */
    .zero 32
    .globl led_frame_count
led_frame_count:
    .zero 4

    .section .rodata.led,"a",@progbits
    .balign 4
/* Color indices U,F,L,R,B,D: white, green, orange, red, blue, yellow. */
led_palette:
    .word 0xffffff, 0x00c050, 0xff8000, 0xff2020, 0x2080ff, 0xffff00
/* Cyclic local face orders, same handedness at all eight corners. */
led_corner_faces:
    .byte 0,1,2, 0,3,1, 5,1,3, 5,2,1
    .byte 0,4,3, 5,3,4, 5,4,2, 0,2,4
/* facelet descriptor: position, local face slot, pixel x, pixel y.
 * Exterior net U / L F R B / D; each facelet is 4 by 3 LEDs. */
led_facelets:
    .byte 7,0,9,0, 4,0,13,0, 0,0,9,3, 1,0,13,3
    .byte 7,1,0,7, 0,2,4,7, 6,2,0,10, 3,1,4,10
    .byte 0,1,9,7, 1,2,13,7, 3,2,9,10, 2,1,13,10
    .byte 1,1,18,7, 4,2,22,7, 2,2,18,10, 5,1,22,10
    .byte 4,1,27,7, 7,2,31,7, 5,2,27,10, 6,1,31,10
    .byte 3,0,9,14, 2,0,13,14, 6,0,9,17, 5,0,13,17
/* Physical quarter-turns, destination <- source, including fixed 0. */
led_turns:
    .byte 0,2,5,3,1,4,6,7, 0,1,2,0,2,1,0,0
    .byte 0,1,2,3,5,6,7,4, 0,0,0,0,1,2,1,2
    .byte 0,1,3,6,4,2,5,7, 0,0,0,0,0,0,0,0

    .section .text.led_begin,"ax",@progbits
    .globl led_begin
    .type led_begin,@function
led_begin:                       /* a0 = already validated input */
    li t0, LED_MATRIX_0_WIDTH
    li t1, 35
    bne t0, t1, .Lled_bad_size
    li t0, LED_MATRIX_0_HEIGHT
    li t1, 25
    bne t0, t1, .Lled_bad_size
    addi sp, sp, -16
    sw ra, 12(sp)
    la t0, led_state
    sb zero, 0(t0)
    sb zero, 8(t0)
    addi t0, t0, 1
    li t1, 7
.Lled_init:
    lbu t2, 0(a0)
    addi t2, t2, -48
    sb t2, 0(t0)
    lbu t2, 7(a0)
    addi t2, t2, -49
    sb t2, 8(t0)
    addi a0, a0, 1
    addi t0, t0, 1
    addi t1, t1, -1
    bnez t1, .Lled_init
    la t0, led_frame_count
    sw zero, 0(t0)
    /* Clear all 35*25 pixels once, using exported geometry, no multiply. */
    li t0, LED_MATRIX_0_BASE
    li t1, LED_MATRIX_0_HEIGHT
.Lled_clear_row:
    li t2, LED_MATRIX_0_WIDTH
.Lled_clear_pixel:
    sw zero, 0(t0)
    addi t0, t0, 4
    addi t2, t2, -1
    bnez t2, .Lled_clear_pixel
    addi t1, t1, -1
    bnez t1, .Lled_clear_row
    call led_draw
    call led_pause
    li a0, 1
    lw ra, 12(sp)
    addi sp, sp, 16
    ret
.Lled_bad_size:
    li a0, 0
    ret
    .size led_begin, .-led_begin

    .section .text.led_animate,"ax",@progbits
    .globl led_animate
    .type led_animate,@function
led_animate:                     /* a0 = solver result_path, a1 = length */
    addi sp, sp, -32
    sw ra, 28(sp)
    sw s0, 24(sp)
    sw s1, 20(sp)
    mv s0, a0
    mv s1, a1
.Lled_next:
    beqz s1, .Lled_animation_done
    lbu t0, 0(s0)
    addi s0, s0, 1
    li t1, 3
    bltu t0, t1, .Lled_R
    li t1, 6
    bltu t0, t1, .Lled_B
    li a0, 2
    addi t0, t0, -5
    j .Lled_turn_count
.Lled_B:
    li a0, 1
    addi t0, t0, -2
    j .Lled_turn_count
.Lled_R:
    li a0, 0
    addi t0, t0, 1
.Lled_turn_count:
    sw a0, 0(sp)
    sw t0, 4(sp)
.Lled_quarter:
    lw a0, 0(sp)
    call led_quarter
    lw t0, 4(sp)
    addi t0, t0, -1
    sw t0, 4(sp)
    bnez t0, .Lled_quarter
    /* HTM: a half/inverse turn is one emitted move and one new frame. */
    call led_draw
    call led_pause
    addi s1, s1, -1
    j .Lled_next
.Lled_animation_done:
    lw s1, 20(sp)
    lw s0, 24(sp)
    lw ra, 28(sp)
    addi sp, sp, 32
    ret
    .size led_animate, .-led_animate

    .section .text.led_quarter,"ax",@progbits
    .globl led_quarter
    .type led_quarter,@function
led_quarter:                     /* a0 = R/B/D face 0..2; leaf */
    slli t0, a0, 4
    la t1, led_turns
    add t1, t1, t0
    la t2, led_state
    li t3, 0
.Lled_transform:
    lbu t4, 0(t1)
    la t5, led_state
    add t5, t5, t4
    lbu t4, 0(t5)
    sb t4, 16(t2)
    lbu t4, 8(t5)
    lbu t5, 8(t1)
    add t4, t4, t5
    li t5, 3
    bltu t4, t5, .Lled_twist_ready
    addi t4, t4, -3
.Lled_twist_ready:
    sb t4, 24(t2)
    addi t1, t1, 1
    addi t2, t2, 1
    addi t3, t3, 1
    li t4, 8
    bltu t3, t4, .Lled_transform
    la t0, led_state
    li t1, 4
.Lled_copy:
    lw t2, 16(t0)
    sw t2, 0(t0)
    addi t0, t0, 4
    addi t1, t1, -1
    bnez t1, .Lled_copy
    ret
    .size led_quarter, .-led_quarter

    .section .text.led_draw,"ax",@progbits
    .globl led_draw
    .type led_draw,@function
led_draw:                        /* leaf, a/t registers only */
    la a0, led_facelets
    li a1, 24
.Lled_facelet:
    lbu t0, 0(a0)
    la t1, led_state
    add t1, t1, t0
    lbu t2, 0(t1)                /* occupant cubie */
    lbu t3, 8(t1)               /* twist at destination */
    lbu t0, 1(a0)               /* local slot k */
    add t0, t0, t3              /* home color index (k + o) mod 3 */
    li t1, 3
    bltu t0, t1, .Lled_color_slot
    addi t0, t0, -3
.Lled_color_slot:
    slli t1, t2, 1
    add t1, t1, t2              /* 3 * cubie */
    add t1, t1, t0
    la t2, led_corner_faces
    add t1, t1, t2
    lbu t0, 0(t1)
    slli t0, t0, 2
    la t1, led_palette
    add t0, t0, t1
    lw a2, 0(t0)
    lbu t0, 2(a0)               /* x */
    lbu t1, 3(a0)               /* y */
    li t2, LED_MATRIX_0_WIDTH
    slli a4, t2, 2              /* row stride in bytes */
    li a3, LED_MATRIX_0_BASE
.Lled_row_offset:
    beqz t1, .Lled_x_offset
    add a3, a3, a4
    addi t1, t1, -1
    j .Lled_row_offset
.Lled_x_offset:
    slli t0, t0, 2
    add a3, a3, t0
    li a5, 3
.Lled_paint_row:
    mv t0, a3
    li t1, 4
.Lled_paint_pixel:
    sw a2, 0(t0)
    addi t0, t0, 4
    addi t1, t1, -1
    bnez t1, .Lled_paint_pixel
    add a3, a3, a4
    addi a5, a5, -1
    bnez a5, .Lled_paint_row
    addi a0, a0, 4
    addi a1, a1, -1
    bnez a1, .Lled_facelet
    /* Written only after the complete frame, useful as a debugger breakpoint. */
    la t0, led_frame_count
    lw t1, 0(t0)
    addi t1, t1, 1
    sw t1, 0(t0)
    ret
    .size led_draw, .-led_draw

    .section .text.led_pause,"ax",@progbits
    .globl led_pause
    .type led_pause,@function
led_pause:
    li t0, LED_DELAY
.Lled_wait:
    beqz t0, .Lled_wait_done
    addi t0, t0, -1
    j .Lled_wait
.Lled_wait_done:
    ret
    .size led_pause, .-led_pause
    .endif
