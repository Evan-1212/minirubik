.text
.globl main

main:
    li t0, 0x20000000
    li t1, 1000000
    li t2, 0x12345678

loop:
    sw t2, 0(t0)
    addi t1, t1, -1
    bnez t1, loop

    li a7, 10
    ecall