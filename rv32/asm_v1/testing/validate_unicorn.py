#!/usr/bin/env python3
"""Optional supplementary diagnostic; NOT Ripes or the final target gate.
Requires Unicorn, pyelftools, and host cc. Run after asm_v1/build.py.
"""
import ctypes
import datetime
import hashlib
import json
import random
import re
import struct
import subprocess
import time
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_INTR, UC_HOOK_MEM_WRITE
from unicorn.riscv_const import UC_RISCV_REG_X0, UC_RISCV_REG_PC
import unicorn
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BUILD = ROOT/'rv32/build/asm-v1'
OUT = BUILD/'supplementary'
OUT.mkdir(exist_ok=True)
cc_sources = [HERE/'oracle_bridge.c', ROOT/'optimized/v1.c', ROOT/'optimized/v1_tables.c',
              ROOT/'optimized_v2/v2.c', ROOT/'optimized_v2/v2_tables.c']
command = ['cc','-shared','-fPIC','-O2',*[str(p) for p in cc_sources],'-o',str(OUT/'oracle.so')]
subprocess.run(command, check=True)
lib = ctypes.CDLL(str(OUT/'oracle.so'))
lib.test_init()
lib.test_distance.argtypes = [ctypes.c_uint]
lib.test_distance.restype = ctypes.c_uint
lib.test_encode.argtypes = [ctypes.c_uint, ctypes.c_void_p]
lib.test_physical_replay.argtypes = [ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
lib.v1_parse.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
lib.test_h.argtypes = [ctypes.c_uint, ctypes.c_uint]
lib.test_h.restype = ctypes.c_uint

def encoded(rank):
    out = ctypes.create_string_buffer(15)
    lib.test_encode(rank, out)
    return out.value.decode('ascii')

def rank_of(s):
    coord = (ctypes.c_uint16*2)()
    assert lib.v1_parse(s.encode(),coord)
    return coord[0]*729+coord[1]

class Machine:
    def __init__(self, path):
        self.path = path
        self.uc = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32)
        self.uc.mem_map(0, 0x400000)
        with path.open('rb') as f:
            elf = ELFFile(f)
            self.entry = elf.header['e_entry']
            self.symbols = {s.name:s.entry['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
            for seg in elf.iter_segments():
                if seg['p_type']=='PT_LOAD': self.uc.mem_write(seg['p_vaddr'],seg.data())
        self.bottom = self.symbols['__stack_bottom']
        self.top = self.symbols['__stack_top']
        self.stack_low = self.top
        self.exited = False
        def intr(uc, number, _):
            assert number==8 and self.reg(17)==10, ('unexpected trap',number,self.reg(17))
            self.exited = True
            uc.emu_stop()
        def write(uc, access, addr, size, value, _):
            self.stack_low=min(self.stack_low,addr)
        self.uc.hook_add(UC_HOOK_INTR,intr)
        self.uc.hook_add(UC_HOOK_MEM_WRITE,write,begin=self.bottom,end=self.top-1)
    def reg(self,n): return self.uc.reg_read(UC_RISCV_REG_X0+n)
    def put(self,n,x): self.uc.reg_write(UC_RISCV_REG_X0+n,x & 0xffffffff)
    def prepare(self):
        for n in range(1,32): self.put(n,0x12340000+n*37)
        self.put(1,0x300000)
        self.put(2,self.top)
        self.put(3,self.symbols['__global_pointer$'])
        self.stack_low=self.top
        self.exited=False
    def call(self,name,args,until=None):
        self.prepare()
        for n,x in enumerate(args): self.put(10+n,x)
        preserved={n:self.reg(n) for n in [2,3,4,8,9,*range(18,28)]}
        dest=0x300000 if until is None else until
        self.uc.emu_start(self.symbols[name],dest,timeout=10_000_000,count=50_000_000)
        assert self.uc.reg_read(UC_RISCV_REG_PC)==dest, ('timeout or limit',name)
        if until is None:
            assert {n:self.reg(n) for n in preserved}==preserved, ('ABI clobber',name)
        return self.reg(10)
    def entry_run(self):
        self.prepare()
        self.uc.emu_start(self.entry,0x300000,timeout=10_000_000,count=50_000_000)
        assert self.exited and self.reg(25)==0x600d
        return self.reg(26),self.reg(27)

begin=time.monotonic()
entry_results=[]
for case in json.loads((BUILD/'cases.json').read_text()):
    machine=Machine(BUILD/case['elf'])
    status,length=machine.entry_run()
    assert status==0 and length==case['expected_length']
    path=bytes(machine.uc.mem_read(machine.symbols['result_path'],length))
    assert lib.test_physical_replay(rank_of(case['input']),path,length)
    entry_results.append(dict(case=case['case'],input=case['input'],length=length,status=status,
                              stack_written_bytes=machine.top-machine.stack_low,
                              elf_sha256=hashlib.sha256((BUILD/case['elf']).read_bytes()).hexdigest()))
print('PASS: complete executables and independent physical replay',flush=True)

m=Machine(BUILD/'solved.elf')
INPUT=0x250000
OUTPUT=0x250100
PATH=0x250200
parser_count=0
for rank in [p*729 for p in range(5040)]+list(range(729)):
    state=encoded(rank)
    m.uc.mem_write(INPUT,state.encode()+b'\0')
    assert m.call('asm_parse',[INPUT,OUTPUT])==1
    p,o=struct.unpack('<HH',bytes(m.uc.mem_read(OUTPUT,4)))
    assert p*729+o==rank, ('parser',rank,state,p,o)
    assert m.top-m.stack_low<=16
    parser_count+=1
print(f'PASS: parser covers all permutations and all orientation coordinates ({parser_count} cases)',flush=True)
invalid=[b'12345671111111'[:i] for i in range(14)]
invalid += [s.encode() for s in ['123456711111111','02345671111111','82345671111111',
           '12345671111110','12345671111114','1234567111111a','11345671111111',
           '12345671111112','1234567111111é']]
for value in invalid:
    m.uc.mem_write(INPUT,value+b'\0')
    assert m.call('asm_parse',[INPUT,OUTPUT])==0, ('invalid accepted',value)
for size in range(14):
    value=b'12345671111111'[:size]+b'\0'
    addr=0x400000-len(value)
    m.uc.mem_write(addr,value)
    assert m.call('asm_parse',[addr,OUTPUT])==0
assert m.call('asm_parse',[0,OUTPUT])==0
assert m.call('asm_parse',[INPUT,0])==0
print('PASS: malformed input, early-NUL page boundary, and null-pointer rejection',flush=True)
# Stop actual solver instructions before root goal test; s3 must equal h(root).
disassembly=(BUILD/'solved.disasm.txt').read_text()
match=re.search(r'^\s*([0-9a-f]+):\s+[0-9a-f]+\s+or\s+t0,s10,s11\s*$',disassembly,re.M)
assert match
bound_ready=int(match[1],16)
projection=bytes(m.uc.mem_read(m.symbols['v2_projection'],5040))
representatives={q:projection.index(q) for q in range(210)}
lookup_count=0
for q,p in representatives.items():
    for o in [0,1,727,728]:
        m.call('asm_solve',[p,o,PATH],until=bound_ready)
        assert m.reg(19)==lib.test_h(p,o),('root heuristic',p,o,q,m.reg(19))
        lookup_count+=1
print(f'PASS: root heuristic on all 210 rows, odd/even and row ends ({lookup_count} cases)',flush=True)
ranks={0,720*729,5040*729-1,1,728,5039*729}
for line in (ROOT/'tests/solutions.txt').read_text().splitlines():
    if line and not line.startswith('#'): ranks.add(rank_of(line.split('|')[0]))
for s in ['25314672313211','54721631111111','41532672313211']: ranks.add(rank_of(s))
ranks.update(random.Random(20261005).sample(range(5040*729),48))
for q in [0,1,179,180,209]:
    for o in [0,1,727,728]: ranks.add(representatives[q]*729+o)
search_results=[]
for rank in sorted(ranks):
    p,o=divmod(rank,729)
    m.uc.mem_write(PATH,b'\xa5'*16)
    n=m.call('asm_solve',[p,o,PATH])
    assert n==lib.test_distance(rank),('optimal length',rank,n,lib.test_distance(rank))
    assert m.top-m.stack_low==48
    path=bytes(m.uc.mem_read(PATH,n))
    assert lib.test_physical_replay(rank,path,n),('physical replay',rank,path)
    assert bytes(m.uc.mem_read(PATH+11,5))==b'\xa5'*5,('path overflow',rank)
    assert all(path[i]//3!=path[i-1]//3 for i in range(1,n))
    assert m.call('asm_replay',[p,o,PATH,n])==1
    search_results.append(dict(input=encoded(rank),rank=rank,length=n,path=list(path)))
for args in [[5040,0,PATH],[0,729,PATH],[0,0,0],[0xffffffff,0,PATH]]:
    assert m.call('asm_solve',args)==0xffffffff
m.uc.mem_write(PATH,b'\x09')
assert m.call('asm_replay',[0,0,PATH,1])==0
for args in [[0,0,PATH,12],[5040,0,PATH,0],[0,729,PATH,0],[0,0,0,0]]:
    assert m.call('asm_replay',args)==0
assert m.call('asm_replay',[1,0,PATH,0])==0
assert m.call('asm_replay',[0,1,PATH,0])==0
print(f'PASS: {len(ranks)} searches against exact BFS and physical replay; ABI/error paths',flush=True)
# Patching only in diagnostic memory; official inputs remain assembled objects.
for state,expected,status in [('11345671111111',-1,1),('12345671111111',1,4),
                              ('25314672313211',-1,0)]:
    machine=Machine(BUILD/'solved.elf')
    machine.uc.mem_write(machine.symbols['cube_input'],state.encode()+b'\0')
    machine.uc.mem_write(machine.symbols['expected_length'],struct.pack('<i',expected))
    actual,_=machine.entry_run()
    assert actual==status
sources=[*cc_sources,HERE/'validate_unicorn.py',ROOT/'optimized_v2/host_oracle.h',
         ROOT/'optimized/host_reference.h',ROOT/'solver.c',
         *sorted((ROOT/'rv32/asm_v1').glob('*.S')),ROOT/'rv32/start.S',ROOT/'rv32/link.ld']
report=dict(status='PASS', environment='Supplementary Unicorn RV32 execution, NOT Ripes',
    unicorn_version=unicorn.__version__, timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    limitations='No final Ripes performance or pipeline claim; search sample is not exhaustive.',
    native_oracle='Independent complete BFS from original cubie-level moves; histogram validated',
    native_oracle_build_command=command,
    source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
    entry_results=entry_results, parser_valid_cases=parser_count,
    parser_invalid_strings=len(invalid), early_nul_boundary_cases=14,
    heuristic_boundary_cases=lookup_count,search_cases=len(ranks),
    abi_checks='s0..s11, sp, gp, tp restored on every completed direct call',
    maximum_stack_bytes_by_call_graph=80,search_results=search_results,
    validation_seconds=time.monotonic()-begin)
(OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('SUPPLEMENTARY_VALIDATION=PASS; output: '+str(OUT/'validation.json'))
