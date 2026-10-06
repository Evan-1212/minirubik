.section .rodata.input,"a",@progbits
.globl cube_input
cube_input:
.asciz "34567212223232"
.balign 4
.globl expected_length
expected_length:
.word 11
