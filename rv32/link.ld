OUTPUT_ARCH(riscv)
ENTRY(_start)
PHDRS
{
    code PT_LOAD FLAGS(5);
    constants PT_LOAD FLAGS(4);
    working PT_LOAD FLAGS(6);
}
SECTIONS
{
    /* Keep address zero unused; Ripes also imports ELF metadata sections. */
    . = 0x1000;
    .text : { KEEP(*(.text.start)) *(.text .text.*) } :code
    . = ALIGN(16);
    .rodata : { *(.rodata .rodata.* .srodata .srodata.*) } :constants
    . = ALIGN(16);
    .data : { *(.data .data.* .sdata .sdata.*) } :working
    __global_pointer$ = ADDR(.data) + 0x800;
    . = ALIGN(16);
    .bss (NOLOAD) :
    {
        __bss_start = .;
        *(.bss .bss.* .sbss .sbss.*)
        *(COMMON)
        . = ALIGN(16);
        __bss_zero_end = .;
        __stack_bottom = .;
        . += 4096;
        __stack_top = .;
    } :working
    ASSERT(SIZEOF(.rodata) + SIZEOF(.data) + SIZEOF(.bss) <= 131072,
           "Static data including the reserved stack exceeds 128 KiB")
}
