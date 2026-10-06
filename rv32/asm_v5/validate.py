#!/usr/bin/env python3
"""Supplementary parser/ABI/integration checks; not official Ripes counts.
Requires Unicorn 2.1.4, pyelftools and host cc. Run after build.py.
"""
import ctypes
import datetime
import hashlib
import json
import platform
import struct
import subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_INTR, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_READ, UC_MEM_WRITE
from unicorn.riscv_const import UC_RISCV_REG_X0, UC_RISCV_REG_PC
import unicorn

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BUILD = ROOT/'rv32/build/asm-v5'
OUT = BUILD/'supplementary'
OUT.mkdir(parents=True, exist_ok=True)
cc_sources = [ROOT/'rv32/asm_v1/testing/oracle_bridge.c', ROOT/'optimized/v1.c',
              ROOT/'optimized/v1_tables.c', ROOT/'optimized_v2/v2.c', ROOT/'optimized_v2/v2_tables.c']
command = ['cc','-shared','-fPIC','-O2',*map(str,cc_sources),'-o',str(OUT/'oracle.so')]
subprocess.run(command,check=True)
lib = ctypes.CDLL(str(OUT/'oracle.so'))
lib.test_init()
lib.test_distance.argtypes = [ctypes.c_uint]
lib.test_distance.restype = ctypes.c_uint
lib.test_encode.argtypes = [ctypes.c_uint,ctypes.c_void_p]
lib.test_physical_replay.argtypes = [ctypes.c_uint,ctypes.c_void_p,ctypes.c_uint]
lib.v1_parse.argtypes = [ctypes.c_char_p,ctypes.c_void_p]


def encoded(rank):
    out = ctypes.create_string_buffer(15)
    lib.test_encode(rank,out)
    return out.value


def reference(value):
    coord = (ctypes.c_uint16*2)()
    valid = bool(lib.v1_parse(value,coord))
    return valid,tuple(coord) if valid else None


class Machine:
    def __init__(self,path):
        self.uc = Uc(UC_ARCH_RISCV,UC_MODE_RISCV32)
        self.uc.mem_map(0,0x400000)
        with path.open('rb') as f:
            elf = ELFFile(f)
            self.entry = elf.header['e_entry']
            self.symbols = {s.name:s.entry['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
            for seg in elf.iter_segments():
                if seg['p_type']=='PT_LOAD':
                    self.uc.mem_write(seg['p_vaddr'],seg.data())
        self.bottom,self.top = self.symbols['__stack_bottom'],self.symbols['__stack_top']
        self.parser_ranges = None

        def intr(uc,number,_):
            assert number==8 and self.reg(17)==10
            self.exited = True
            uc.emu_stop()

        def write(uc,access,addr,size,value,_):
            self.stack_low = min(self.stack_low,addr)

        def parser_memory(uc,access,addr,size,value,_):
            if self.parser_ranges is None:
                return
            input_start,input_end,output = self.parser_ranges
            stack = self.top-16 <= addr and addr+size <= self.top
            if access == UC_MEM_WRITE:
                allowed = stack or output <= addr and addr+size <= output+4
            else:
                allowed = stack or input_start <= addr and addr+size <= input_end
            assert allowed, ('parser memory outside input/output/local stack',addr,size,access)

        self.uc.hook_add(UC_HOOK_INTR,intr)
        self.uc.hook_add(UC_HOOK_MEM_WRITE,write,begin=self.bottom,end=self.top-1)
        self.uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE,parser_memory)

    def reg(self,n):
        return self.uc.reg_read(UC_RISCV_REG_X0+n)

    def put(self,n,value):
        self.uc.reg_write(UC_RISCV_REG_X0+n,value & 0xffffffff)

    def prepare(self):
        for n in range(1,32):
            self.put(n,0x12340000+n*37)
        self.put(1,0x300000)
        self.put(2,self.top)
        self.put(3,self.symbols['__global_pointer$'])
        self.stack_low,self.exited = self.top,False

    def call(self,name,args):
        self.prepare()
        for n,value in enumerate(args):
            self.put(10+n,value)
        saved = {n:self.reg(n) for n in [2,3,4,8,9,*range(18,28)]}
        self.uc.emu_start(self.symbols[name],0x300000,timeout=15_000_000,count=50_000_000)
        assert self.uc.reg_read(UC_RISCV_REG_PC)==0x300000,'Timeout or instruction limit'
        assert {n:self.reg(n) for n in saved}==saved,'ABI clobber'
        return self.reg(10)

    def entry_run(self):
        self.prepare()
        self.uc.emu_start(self.entry,0x300000,timeout=15_000_000,count=50_000_000)
        assert self.exited and self.reg(25)==0x600d
        return self.reg(26),self.reg(27)


entries = []
for case in json.loads((BUILD/'cases.json').read_text()):
    m = Machine(BUILD/case['elf'])
    status,length = m.entry_run()
    assert status==0 and length==case['expected_length']
    valid,(p,o) = reference(case['input'].encode())
    rank = p*729+o
    path = bytes(m.uc.mem_read(m.symbols['result_path'],length))
    assert valid and length==lib.test_distance(rank)
    assert lib.test_physical_replay(rank,path,length)
    assert case['text_bytes']==1428 and case['static_data_bytes']==126488
    assert m.top-m.stack_low==(48 if rank==0 else 80)
    entries.append(dict(case=case['case'],input=case['input'],length=length,status=status,
        stack_written_bytes=m.top-m.stack_low,elf_sha256=case['elf_sha256']))
print('PASS: 3 complete executables, exact distances, physical replay, stack limits',flush=True)

m = Machine(BUILD/'solved.elf')
INPUT,OUTPUT,PATH = 0x250000,0x250100,0x250200
parser_totals = {'valid':0,'invalid':0}


def check_parse(value,expected_rank=None,address=INPUT):
    valid,coord = reference(value)
    if expected_rank is not None:
        assert valid and coord[0]*729+coord[1]==expected_rank
    raw = value+b'\0'
    m.uc.mem_write(address,raw)
    m.uc.mem_write(OUTPUT-4,b'\xa5'*12)
    m.parser_ranges = (address,address+len(raw),OUTPUT)
    try:
        result = m.call('asm_parse',[address,OUTPUT])
    finally:
        m.parser_ranges = None
    assert result==int(valid),('parse result',value,result,valid)
    actual = bytes(m.uc.mem_read(OUTPUT-4,12))
    assert actual[:4]==b'\xa5'*4 and actual[8:]==b'\xa5'*4,'Output overflow'
    if valid:
        assert struct.unpack('<HH',actual[4:8])==coord,('coordinates',value,coord,actual)
    else:
        assert actual==b'\xa5'*12,'Failed parse changed output'
    assert bytes(m.uc.mem_read(address,len(raw)))==raw,'Input modified'
    assert m.top-m.stack_low <= 16
    parser_totals['valid' if valid else 'invalid'] += 1


for rank in [p*729 for p in range(5040)]+list(range(729)):
    check_parse(encoded(rank),rank)
print('PASS: parser covers all 5040 permutations and all 729 orientation coordinates',flush=True)

# Each orientation coordinate must accept exactly its required seventh trit.
for o in range(729):
    value = encoded(o)
    for trit in b'123':
        check_parse(value[:13]+bytes([trit]))
print('PASS: all 2187 orientation/seventh-trit combinations match the native parser',flush=True)

# Exhaustive single-byte replacement checks both alphabets, duplicates, NULs
# and non-ASCII bytes. Mutating the terminator tests rejection of trailing data.
base = b'12345671111111\0'
for position in range(15):
    for byte in range(256):
        value = base[:position]+bytes([byte])+base[position+1:]
        check_parse(value)
for size in range(14):
    value = b'12345671111111'[:size]
    check_parse(value,address=0x400000-len(value)-1)
check_parse(b'12345671111111',0,address=0x400000-15)
check_parse(b'12345671111111X',address=0x400000-16)
check_parse(encoded(5040*729-1),5040*729-1,address=INPUT+1)
for args in [[0,OUTPUT],[INPUT,0],[0,0]]:
    m.uc.mem_write(OUTPUT,b'\xa5'*4)
    assert m.call('asm_parse',args)==0
    assert bytes(m.uc.mem_read(OUTPUT,4))==b'\xa5'*4
print('PASS: 3840 byte mutations, NUL/page boundaries, unaligned input and null arguments; unchanged failure output',flush=True)

# Re-reading the input must remain safe when aligned output overlaps it:
# all input reads must finish before the final two halfword stores.
overlap_cases = []
for rank in [0,5040*729-1,720*729]:
    value = encoded(rank)+b'\0'
    for offset in range(0,14,2):
        m.uc.mem_write(INPUT,b'\xa5'*32)
        m.uc.mem_write(INPUT,value)
        before = bytes(m.uc.mem_read(INPUT,32))
        assert m.call('asm_parse',[INPUT,INPUT+offset])==1
        after = bytes(m.uc.mem_read(INPUT,32))
        assert struct.unpack('<HH',after[offset:offset+4])==divmod(rank,729)
        assert after[:offset]==before[:offset] and after[offset+4:]==before[offset+4:]
        overlap_cases.append(dict(rank=rank,offset=offset))
print('PASS: 21 aligned input/output overlap cases',flush=True)

previous_path = ROOT/'rv32/asm_v1/supplementary/cloud-validation.json'
previous = json.loads(previous_path.read_text())
assert previous['status']=='PASS'
search_results = []
for case in previous['search_results']:
    rank = case['rank']
    check_parse(case['input'].encode(),rank)
    p,o = struct.unpack('<HH',m.uc.mem_read(OUTPUT,4))
    m.uc.mem_write(PATH,b'\xa5'*16)
    length = m.call('asm_solve',[p,o,PATH])
    path = bytes(m.uc.mem_read(PATH,length))
    assert length==lib.test_distance(rank)==case['length']
    assert list(path)==case['path']
    assert lib.test_physical_replay(rank,path,length)
    assert bytes(m.uc.mem_read(PATH+11,5))==b'\xa5'*5
    assert m.top-m.stack_low==(0 if rank==0 else 48)
    assert m.call('asm_replay',[p,o,PATH,length])==1
    search_results.append(dict(input=case['input'],rank=rank,length=length,path=list(path),same_path_as_v1=True))
print(f'PASS: {len(search_results)} parse/solve/replay samples match archived paths and exact BFS; ABI',flush=True)

sources = [HERE/'parse.S',HERE/'validate.py',ROOT/'rv32/asm_v4/solve.S',
           ROOT/'rv32/asm_v1/replay.S',ROOT/'rv32/asm_v1/target.S',previous_path,
           *cc_sources,ROOT/'optimized_v2/host_oracle.h',ROOT/'optimized/host_reference.h',ROOT/'solver.c']
report = dict(status='PASS',timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    environment='Supplementary Unicorn RV32 execution; NOT Ripes',
    platform=platform.platform(),unicorn_version=unicorn.__version__,
    limitations='No official retired-instruction counts; not exhaustive assembly search or the full distance-11 performance gate.',
    source_change='Parser pointer traversal, invariant constants, direct input comparisons and separate seventh-trit validation; reuse v4 solver unchanged',
    build_provenance=json.loads((BUILD/'provenance.json').read_text()),
    source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
    native_oracle_build_command=command,entry_results=entries,
    coordinate_sweep_cases=5769,orientation_checksum_cases=2187,byte_mutation_cases=3840,
    early_nul_boundary_cases=14,full_string_boundary_cases=2,unaligned_input_cases=1,
    null_argument_cases=3,parser_totals=parser_totals,overlap_cases=overlap_cases,
    parser_memory_checks='Only input reads, local-stack reads/writes and four output bytes; canaries and unchanged output on failure',
    abi_checks='sp, gp, tp, s0..s11 preserved on every completed direct call',
    search_results=search_results,solver_sample_count=len(search_results))
(OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('ASM_V5_SUPPLEMENTARY_VALIDATION=PASS',flush=True)
