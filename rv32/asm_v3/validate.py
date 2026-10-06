#!/usr/bin/env python3
"""Supplementary validation of the solved-root early return; not Ripes."""
import ctypes
import datetime
import hashlib
import json
import platform
import re
import struct
import subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_INTR, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_READ, UC_HOOK_CODE
from unicorn.riscv_const import UC_RISCV_REG_X0, UC_RISCV_REG_PC
import unicorn

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BUILD = ROOT / 'rv32/build/asm-v3'
OUT = BUILD / 'supplementary'
OUT.mkdir(parents=True, exist_ok=True)


def instructions(path):
    source = re.sub(r'/\*.*?\*/', '', path.read_text(), flags=re.S)
    return [line.strip() for line in source.splitlines() if line.strip()]

before = instructions(ROOT / 'rv32/asm_v2/solve.S')
after = instructions(HERE / 'solve.S')
def search_body(lines):
    return lines[lines.index('.Lsolve_threshold:'):lines.index('.Lsolve_fail:')]
assert search_body(before) == search_body(after), 'Unexpected search-loop change'

bridge = ROOT / 'rv32/asm_v1/testing/oracle_bridge.c'
cc_sources = [bridge, ROOT/'optimized/v1.c', ROOT/'optimized/v1_tables.c',
              ROOT/'optimized_v2/v2.c', ROOT/'optimized_v2/v2_tables.c']
command = ['cc', '-shared', '-fPIC', '-O2', *map(str, cc_sources), '-o', str(OUT/'oracle.so')]
subprocess.run(command, check=True)
lib = ctypes.CDLL(str(OUT/'oracle.so'))
lib.test_init()
lib.test_distance.argtypes = [ctypes.c_uint]
lib.test_distance.restype = ctypes.c_uint
lib.test_physical_replay.argtypes = [ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
lib.v1_parse.argtypes = [ctypes.c_char_p, ctypes.c_void_p]


def rank_of(state):
    coord = (ctypes.c_uint16 * 2)()
    assert lib.v1_parse(state.encode(), coord)
    return coord[0] * 729 + coord[1]


class Machine:
    def __init__(self, path):
        self.uc = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        self.uc.mem_map(0, 0x400000)
        with path.open('rb') as f:
            elf = ELFFile(f)
            self.entry = elf.header['e_entry']
            self.symbols = {s.name:s.entry['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
            for seg in elf.iter_segments():
                if seg['p_type'] == 'PT_LOAD':
                    self.uc.mem_write(seg['p_vaddr'], seg.data())
        self.bottom, self.top = self.symbols['__stack_bottom'], self.symbols['__stack_top']
        self.stack_low, self.exited, self.candidates = self.top, False, 0
        disassembly = path.with_suffix('.disasm.txt').read_text()
        matches = re.findall(r'^\s*([0-9a-f]+):\s+[0-9a-f]+\s+sub\s+a2,s3,a1\s*$', disassembly, re.M)
        assert len(matches) == 1
        address = int(matches[0], 16)

        def invariant(uc, address, size, _):
            depth, bound, child = self.reg(18), self.reg(19), self.reg(11)
            assert 0 <= depth < bound <= 11 and child == depth + 1 <= bound, (depth,bound,child)
            self.candidates += 1

        def intr(uc, number, _):
            assert number == 8 and self.reg(17) == 10
            self.exited = True
            uc.emu_stop()

        def write(uc, access, addr, size, value, _):
            self.stack_low = min(self.stack_low, addr)

        self.uc.hook_add(UC_HOOK_CODE, invariant, begin=address, end=address)
        self.uc.hook_add(UC_HOOK_INTR, intr)
        self.uc.hook_add(UC_HOOK_MEM_WRITE, write, begin=self.bottom, end=self.top-1)

    def reg(self, n):
        return self.uc.reg_read(UC_RISCV_REG_X0+n)

    def put(self, n, value):
        self.uc.reg_write(UC_RISCV_REG_X0+n, value & 0xffffffff)

    def prepare(self):
        for n in range(1,32):
            self.put(n, 0x12340000+n*37)
        self.put(1, 0x300000)
        self.put(2, self.top)
        self.put(3, self.symbols['__global_pointer$'])
        self.stack_low, self.exited, self.candidates = self.top, False, 0

    def call(self, name, args):
        self.prepare()
        for n, value in enumerate(args):
            self.put(10+n, value)
        preserved = {n:self.reg(n) for n in [2,3,4,8,9,*range(18,28)]}
        self.uc.emu_start(self.symbols[name], 0x300000, timeout=15_000_000, count=50_000_000)
        assert self.uc.reg_read(UC_RISCV_REG_PC) == 0x300000, 'Timeout or instruction limit'
        assert {n:self.reg(n) for n in preserved} == preserved, 'ABI clobber'
        return self.reg(10)

    def entry_run(self):
        self.prepare()
        self.uc.emu_start(self.entry, 0x300000, timeout=15_000_000, count=50_000_000)
        assert self.exited and self.reg(25) == 0x600d
        return self.reg(26), self.reg(27)


entry_results = []
for case in json.loads((BUILD/'cases.json').read_text()):
    m = Machine(BUILD/case['elf'])
    status, length = m.entry_run()
    assert status == 0 and length == case['expected_length']
    path = bytes(m.uc.mem_read(m.symbols['result_path'], length))
    rank = rank_of(case['input'])
    assert length == lib.test_distance(rank)
    assert lib.test_physical_replay(rank, path, length)
    assert case['text_bytes'] == 1468 and case['static_data_bytes'] == 126488
    assert m.top-m.stack_low == (48 if rank == 0 else 80)
    entry_results.append(dict(case=case['case'], input=case['input'], status=status,
                              length=length, candidate_visits=m.candidates,
                              stack_written_bytes=m.top-m.stack_low,
                              elf_sha256=case['elf_sha256']))
print('PASS: 3 complete executables, exact distances and physical replay', flush=True)

previous_path = ROOT/'rv32/asm_v1/supplementary/cloud-validation.json'
previous = json.loads(previous_path.read_text())
assert previous['status'] == 'PASS'
v2_path = ROOT/'rv32/asm_v2/supplementary/cloud-validation.json'
v2 = json.loads(v2_path.read_text())
assert v2['status'] == 'PASS'
v2_index = {r['input']:r for r in v2['search_results']}
m = Machine(BUILD/'solved.elf')
PATH = 0x250200
results = []
for case in previous['search_results']:
    rank = case['rank']
    p,o = divmod(rank,729)
    m.uc.mem_write(PATH, b'\xa5'*16)
    length = m.call('asm_solve', [p,o,PATH])
    candidate_visits = m.candidates
    path = bytes(m.uc.mem_read(PATH,length))
    assert length == lib.test_distance(rank) == case['length']
    assert list(path) == case['path'], ('Changed search path',case['input'])
    assert lib.test_physical_replay(rank,path,length)
    assert bytes(m.uc.mem_read(PATH+11,5)) == b'\xa5'*5
    assert m.top-m.stack_low == (0 if rank == 0 else 48)
    reference = v2_index[case['input']]
    assert reference['same_path_as_v1'] and reference['length'] == length
    assert reference['candidate_visits'] == candidate_visits
    assert m.call('asm_replay',[p,o,PATH,length]) == 1
    results.append(dict(input=case['input'], length=length, candidate_visits=candidate_visits,
                        same_path_as_v1=True, same_path_and_candidate_count_as_v2=True))
print(f'PASS: {len(results)} solver samples match preserved paths, v2 candidate counts, exact BFS and physical replay; ABI',flush=True)
print('PASS: depth invariant at every candidate in the sampled executions',flush=True)

# Exercise the new paths with data-access hooks. They must return before any
# data load/store, leaving the output, saved registers and stack untouched.
fast_cases = [
    ([0,0,PATH], 0),
    ([0,0,0x3fffff], 0),
    ([0,0,0], 0xffffffff),
    ([1,0,0], 0xffffffff),
    ([5040,0,PATH], 0xffffffff),
    ([0,729,PATH], 0xffffffff),
    ([5039,729,PATH], 0xffffffff),
    ([5040,728,PATH], 0xffffffff),
    ([0xffffffff,0,PATH], 0xffffffff),
    ([0,0xffffffff,PATH], 0xffffffff),
]
early_results = []
for args, expected in fast_cases:
    accesses = []
    executed = []
    memory_hook = m.uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE,
        lambda uc, access, address, size, value, _: accesses.append((access,address,size)))
    code_hook = m.uc.hook_add(UC_HOOK_CODE,
        lambda uc, address, size, _: executed.append(address))
    try:
        value = m.call('asm_solve',args)
    finally:
        m.uc.hook_del(memory_hook)
        m.uc.hook_del(code_hook)
    assert value == expected and m.candidates == 0
    assert m.top-m.stack_low == 0 and not accesses, ('Early path data access',args,accesses)
    early_results.append(dict(arguments=args, return_value=value, data_accesses=len(accesses),
                              stack_written_bytes=0, emulator_instruction_visits=len(executed)))
print('PASS: 2 solved and 8 invalid-argument early returns preserve ABI, touch no data memory and use no stack',flush=True)

sources = [HERE/'solve.S', HERE/'validate.py', previous_path, v2_path, *cc_sources,
           ROOT/'optimized_v2/host_oracle.h', ROOT/'optimized/host_reference.h', ROOT/'solver.c']
report = dict(status='PASS', timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    environment='Supplementary Unicorn RV32 execution; NOT Ripes',
    platform=platform.platform(), unicorn_version=unicorn.__version__,
    limitations='No official retired-instruction counts; not exhaustive assembly validation or the full distance-11 gate.',
    source_change='Argument checks and solved-root detection precede stack setup; search loop unchanged from v2',
    build_provenance=json.loads((BUILD/'provenance.json').read_text()),
    source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
    native_oracle_build_command=command, entry_results=entry_results,
    early_return_cases=early_results,
    solver_sample_count=len(results), sampled_candidate_visits=sum(r['candidate_visits'] for r in results),
    abi_checks='sp, gp, tp, s0..s11 preserved on every completed direct call',search_results=results)
(OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('ASM_V3_SUPPLEMENTARY_VALIDATION=PASS',flush=True)
