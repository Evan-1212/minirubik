"""Shared host utilities for the fixed asm-v5 distance-11 gate (stdlib only)."""
import csv
import hashlib
import json
import os
import struct
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BUILD = ROOT / 'rv32/build/distance11'
REFERENCE = ROOT / 'measurements/stage4-asm-v5/20261006T085548Z-RV32_ISS-051199'
CSV = ROOT / 'measurements/2026-10-05-stage3/v2-distance11.csv'
BASE_COMMIT = 'de9e008c02db76f6dd1ee63f39ff035af9e6b495'
RIPES_SHA = 'bd2ddea8cd6fcf6902cda7366fe99ab6dd0c7fdbbc7efcfdb89ede20acc67f0f'
PREFIX = 'riscv64-unknown-elf-'
LIMIT = 50_000_000
COUNT = 2644


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def atomic(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.tmp')
    with temp.open('w', encoding='utf-8') as f:
        json.dump(value, f, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    temp.replace(path)


def source_hashes():
    names = read(HERE/'baseline-files.json')['sha256']
    result = {}
    for name, expected in names.items():
        require(sha(ROOT/name) == expected, 'Preserved file changed: '+name)
        result[name] = expected
    for p in sorted(HERE.rglob('*')):
        if p.is_file() and p.suffix in ('.py', '.c', '.md', '.json') and '__pycache__' not in p.parts and 'supplementary' not in p.parts:
            result[str(p.relative_to(ROOT))] = sha(p)
    return result


def check_sources(manifest):
    require(source_hashes() == manifest['sources'],
            'Source changed since preparation; do not mix different builds in one run.')


def state_rank(state):
    require(len(state) == 14 and sorted(state[:7]) == list('1234567') and
            all(c in '123' for c in state[7:]) and
            sum(int(c)-1 for c in state[7:]) % 3 == 0, 'Invalid cube input')
    p = o = 0
    for i, digit in enumerate(state[:7]):
        p = p*(7-i) + sum(other < digit for other in state[i+1:7])
    for digit in state[7:13]:
        o = 3*o + int(digit)-1
    return p*729+o


def load_cases():
    with CSV.open(newline='') as f:
        rows = list(csv.DictReader(f))
    cases = [dict(rank=int(r['rank']), input=r['state'], expected_length=int(r['length'])) for r in rows]
    require(len(cases) == COUNT and len({c['rank'] for c in cases}) == COUNT,
            'Distance-11 list is incomplete or contains duplicates')
    require([c['rank'] for c in cases] == sorted(c['rank'] for c in cases), 'Ranks must be sorted')
    for c in cases:
        require(c['expected_length'] == 11 and state_rank(c['input']) == c['rank'], 'Bad rank/state/length')
    return cases


def input_source(state):
    state_rank(state)
    return ('.section .rodata.input,"a",@progbits\n'
            '.globl cube_input\ncube_input:\n'
            f'.asciz "{state}"\n.balign 4\n'
            '.globl expected_length\nexpected_length:\n.word 11\n')


def symbol_file_offset(path, symbol):
    data = Path(path).read_bytes()
    hdr = struct.unpack_from('<16sHHIIIIIHHHHHH', data)
    require(data[:7] == b'\x7fELF\x01\x01\x01', 'Expected ELF32 LE')
    sections = [struct.unpack_from('<10I', data, hdr[6]+i*hdr[11]) for i in range(hdr[12])]
    found = []
    for section in sections:
        if section[1] != 2:
            continue
        strings = sections[section[6]]
        table = data[strings[4]:strings[4]+strings[5]]
        for offset in range(section[4], section[4]+section[5], section[9]):
            name, value, size, info, other, index = struct.unpack_from('<IIIBBH', data, offset)
            if table[name:].split(b'\0',1)[0].decode() == symbol:
                target = sections[index]
                require(target[1] != 8, 'Symbol is in NOBITS')
                found.append(target[4]+value-target[3])
    require(len(found) == 1, 'Missing/ambiguous symbol: '+symbol)
    return found[0]


def expected_elf(template, offset, state):
    data = bytearray(template)
    data[offset:offset+15] = state.encode('ascii')+b'\0'
    return bytes(data)


def build_case(state, work, objects, template=None, offset=None):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    source, obj, elf = work/'input.S', work/'input.o', work/'case.elf'
    source.write_text(input_source(state))
    commands = [
        [PREFIX+'gcc', '-march=rv32i', '-mabi=ilp32', '-c', str(source), '-o', str(obj)],
        [PREFIX+'gcc', '-march=rv32i', '-mabi=ilp32', '-nostdlib', '-Wl,--gc-sections',
         '-Wl,--build-id=none', '-Wl,-T,'+str(ROOT/'rv32/link.ld'),
         '-Wl,-Map,'+str(work/'case.map'), *map(str, objects), str(obj), '-o', str(elf)]
    ]
    for command in commands:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if template is not None:
        require(elf.read_bytes() == expected_elf(template, offset, state),
                'Linked ELF differs outside cube_input; refusing to reuse the template audit')
    return elf, commands


def validate_report(report, source):
    info = report.get('runinfo', {})
    require(info.get('processor') == 'RV32_ISS' and info.get('ISA extensions') == [],
            'Wrong/missing processor or ISA extensions')
    require(info.get('source file') == source, 'Report belongs to another executable')
    regs = report.get('registers', {})
    def reg(n):
        value = regs.get('x'+str(n))
        require(isinstance(value, (str, int)) and not isinstance(value, bool), 'Missing/invalid register')
        return int(value, 0) if isinstance(value, str) else value
    require(reg(25) == 0x600d and reg(26) == 0 and reg(27) == 11 and reg(17) == 10,
            'Target did not finish replay and length checks successfully')
    iret = report.get('# instructions retired')
    require(type(iret) is int and 0 < iret <= LIMIT, 'Invalid count or 50M limit exceeded')
    return iret
