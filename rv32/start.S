/* Common measurement boundary: startup through the exit ecall. */
    .option norvc
    .section .text.start,"ax",@progbits
    .globl _start
    .type _start,@function
_start:
    .option push
    .option norelax
    la gp, __global_pointer$
    .option pop
    la sp, __stack_top

    /* Explicitly initialize C static workspace. The reserved stack is not
       included in this loop, but is included in the .bss memory budget. */
    la t0, __bss_start
    la t1, __bss_zero_end
1:
    bgeu t0, t1, 2f
    sw zero, 0(t0)
    addi t0, t0, 4
    j 1b
2:
    call target_main
    mv s10, a0                  /* x26: status; zero means success. */
    la t0, result_length
    lw s11, 0(t0)               /* x27: returned solution length. */
    li s9, 0x600d               /* x25: completion marker. */
    li a7, 10                   /* Ripes Exit environment call. */
    ecall
3:
    j 3b
    .size _start, .-_start
