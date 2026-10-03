.text
.globl main

main:
    li t0, 0x20000000
    li t1, 16384
    li t2, 0x12345678

loop:
    sw t2, 0(t0)
    addi t0, t0, 4
    addi t1, t1, -1
    bnez t1, loop

    li t3, 500000

delay:
    addi t3, t3, -1
    bnez t3, delay

    li a7, 10
    ecall