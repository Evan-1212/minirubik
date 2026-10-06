.section .rodata.input,"a",@progbits
.globl cube_input
cube_input:
.asciz "42315673112111"
.balign 4
.globl expected_length
expected_length:
.word 11
