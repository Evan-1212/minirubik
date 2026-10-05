"""Audit an RV32I linked executable using Python stdlib and GNU binutils."""
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

RV32I = set("lui auipc jal jalr beq bne blt bge bltu bgeu lb lh lw lbu lhu "
            "sb sh sw addi slti sltiu xori ori andi slli srli srai add sub "
            "sll slt sltu xor srl sra or and fence ecall ebreak".split())


def inspect(path, prefix="riscv64-unknown-elf-"):
    path = Path(path)
    data = path.read_bytes()
    if data[:7] != b"\x7fELF\x01\x01\x01":
        raise ValueError("Expected little-endian ELF32")
    hdr = struct.unpack_from("<16sHHIIIIIHHHHHH", data)
    if hdr[1] != 2 or hdr[2] != 243 or hdr[7] != 0:
        raise ValueError("Expected a RISC-V executable with base ABI flags")
    shoff, shsize, shnum, stridx = hdr[6], hdr[11], hdr[12], hdr[13]
    headers = [struct.unpack_from("<10I", data, shoff + i * shsize)
               for i in range(shnum)]
    string_header = headers[stridx]
    strings = data[string_header[4]:string_header[4] + string_header[5]]
    sections = []
    for sh in headers:
        name = strings[sh[0]:].split(b"\0", 1)[0].decode()
        sections.append(dict(name=name, address=sh[3], bytes=sh[5], flags=sh[2]))
    allocated = [s for s in sections if s["flags"] & 2]
    executable = [s for s in allocated if s["flags"] & 4]
    if [s["name"] for s in executable] != [".text"]:
        raise ValueError("Unexpected executable sections")
    static_sections = [s for s in allocated if not s["flags"] & 4]
    static_bytes = sum(s["bytes"] for s in static_sections)
    if static_bytes > 131072:
        raise ValueError(f"Static data exceeds budget: {static_bytes}")

    def run(tool, *args):
        return subprocess.check_output([prefix + tool, *args, str(path)], text=True)

    attributes = run("readelf", "-h", "-A", "-W", "-S")
    path.with_suffix(".sections.txt").write_text(attributes)
    if not re.search(r'Tag_RISCV_arch:\s*"rv32i[0-9]+p[0-9]+"', attributes):
        raise ValueError("ELF architecture is not RV32I-only")
    undefined = run("nm", "-u")
    if undefined.strip():
        raise ValueError("Undefined symbols: " + undefined)
    symbols = run("nm", "-n", "-S")
    path.with_suffix(".symbols.txt").write_text(symbols)
    forbidden = re.compile(r"(?:malloc|calloc|realloc|free|sbrk|brk|"
                           r"__(?:u?div|u?mod|mul|[a-z]*[sd]f)[A-Za-z0-9_]*)$")
    for line in symbols.splitlines():
        if line.split() and forbidden.fullmatch(line.split()[-1]):
            raise ValueError("Forbidden runtime dependency: " + line)
    disassembly = run("objdump", "-d", "-M", "no-aliases")
    path.with_suffix(".disasm.txt").write_text(disassembly)
    count = 0
    for line in disassembly.splitlines():
        match = re.match(r"\s*[0-9a-f]+:\s+([0-9a-f]+)\s+(\S+)", line)
        if not match:
            continue
        encoding, opcode = match.groups()
        if len(encoding) != 8 or opcode not in RV32I:
            raise ValueError("Non-RV32I instruction: " + line)
        count += 1
    if count * 4 != executable[0]["bytes"]:
        raise ValueError("Disassembly did not account for every .text byte")
    report = dict(elf=path.name, isa="RV32I", text_bytes=executable[0]["bytes"],
                  static_data_bytes=static_bytes, static_sections=static_sections,
                  reserved_stack_bytes=4096, static_limit_bytes=131072,
                  static_budget_pass=True, undefined_symbols=[],
                  instruction_audit_pass=True)
    path.with_suffix(".audit.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(inspect(sys.argv[1]), indent=2))
