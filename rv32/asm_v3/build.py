#!/usr/bin/env python3
"""Build assembly v3 (solved-root early return); no Python dependencies."""
import argparse
import datetime
import hashlib
import json
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RV32 = HERE.parent
ROOT = RV32.parent
BUILD = RV32 / 'build' / 'asm-v3'
sys.path.insert(0, str(RV32))
from inspect_elf import inspect

PREFIX = 'riscv64-unknown-elf-'
FLAGS = ['-O2', '-march=rv32i', '-mabi=ilp32', '-std=c99', '-ffreestanding',
         '-ffunction-sections', '-fdata-sections', '-Wall', '-Wextra', '-Werror']
TABLES = ['optimized/v1_tables.c', 'optimized_v2/v2_tables.c']
ASM = ['rv32/start.S', 'rv32/asm_v1/parse.S', 'rv32/asm_v3/solve.S',
       'rv32/asm_v1/replay.S', 'rv32/asm_v1/target.S']
CASES = [('solved', '12345671111111', 0),
         ('short', '25314672313211', 1),
         ('distance11', '21345671111111', 11)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', help='Build one arbitrary valid 14-character input')
    parser.add_argument('--expected', type=int, default=-1,
                        help='Optional known optimal length, default -1')
    args = parser.parse_args()
    cases = CASES
    if args.state is not None:
        s = args.state
        if (len(s) != 14 or sorted(s[:7]) != list('1234567') or
            any(c not in '123' for c in s[7:]) or
            sum(int(c) - 1 for c in s[7:]) % 3):
            parser.error('--state must encode a valid cube')
        if not -1 <= args.expected <= 11:
            parser.error('--expected must be -1 or 0..11')
        cases = [('custom', s, args.expected)]
    elif args.expected != -1:
        parser.error('--expected requires --state')
    for tool in ('gcc', 'ld', 'readelf', 'objdump', 'nm'):
        if not shutil.which(PREFIX + tool):
            raise SystemExit('Missing tool: ' + PREFIX + tool)
    baseline = json.loads((HERE/'baseline-files.json').read_text())
    for name, expected in baseline['sha256'].items():
        path = ROOT/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise SystemExit('Preserved reference source differs from the validated starting point: '+name)
    BUILD.mkdir(parents=True, exist_ok=True)
    commands = []

    def run(argv):
        commands.append(argv)
        print(shlex.join(argv), flush=True)
        subprocess.run(argv, cwd=ROOT, check=True)

    objects = []
    for source in TABLES + ASM:
        obj = BUILD / (source.replace('/', '_') + '.o')
        flags = FLAGS if source.endswith('.c') else ['-march=rv32i', '-mabi=ilp32']
        run([PREFIX + 'gcc', *flags, '-c', source, '-o', str(obj)])
        objects.append(str(obj))
    summaries = []
    for label, state, expected in cases:
        input_s = BUILD / (label + '-input.S')
        input_s.write_text('.section .rodata.input,"a",@progbits\n'
                           '.globl cube_input\ncube_input:\n'
                           f'.asciz "{state}"\n.balign 4\n'
                           '.globl expected_length\nexpected_length:\n'
                           f'.word {expected}\n')
        input_o = input_s.with_suffix('.o')
        run([PREFIX + 'gcc', '-march=rv32i', '-mabi=ilp32', '-c', str(input_s),
             '-o', str(input_o)])
        elf = BUILD / (label + '.elf')
        run([PREFIX + 'gcc', '-march=rv32i', '-mabi=ilp32', '-nostdlib',
             '-Wl,--gc-sections', '-Wl,--build-id=none', '-Wl,-T,rv32/link.ld',
             '-Wl,-Map,' + str(elf.with_suffix('.map')),
             *objects, str(input_o), '-o', str(elf)])
        report = inspect(elf)
        symbols = subprocess.check_output([PREFIX+'nm', '-n', str(elf)], text=True)
        live_text = {p[2] for line in symbols.splitlines()
                     if len(p := line.split()) == 3 and p[1] in ('t', 'T')}
        expected_text = {'_start', 'target_main', 'asm_parse', 'asm_solve', 'asm_replay'}
        if live_text != expected_text:
            raise SystemExit('Unexpected executable symbols: ' + repr(live_text))
        report['handwritten_runtime_symbols'] = sorted(live_text)
        report['maximum_stack_bytes_by_call_graph'] = 80
        report['solver_early_return_stack_bytes'] = 0
        elf.with_suffix('.audit.json').write_text(json.dumps(report, indent=2)+'\n')
        summaries.append(dict(case=label, input=state, expected_length=expected,
                              elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
                              **report))
        print(f"AUDIT PASS {label}: .text={report['text_bytes']} B; "
              f"static data including 4096 B stack={report['static_data_bytes']} B")
    sources = [ROOT/p for p in TABLES + ASM] + [ROOT/'optimized/v1.h',
               ROOT/'optimized_v2/v2.h', RV32/'link.ld', RV32/'inspect_elf.py']
    sources += sorted(p for p in HERE.iterdir() if p.is_file())
    sources += [BUILD/(c[0]+'-input.S') for c in cases]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sources}

    def git(*args):
        p = subprocess.run(['git', *args], cwd=ROOT, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return p.stdout.strip() if p.returncode == 0 else None

    provenance = dict(variant='asm-v3',
        timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        platform=platform.platform(), host=platform.node(),
        gcc=subprocess.check_output([PREFIX+'gcc','--version'], text=True).splitlines()[0],
        linker=subprocess.check_output([PREFIX+'ld','--version'], text=True).splitlines()[0],
        source_commit=git('rev-parse','HEAD'), worktree_status=git('status','--short'),
        note='Source hashes identify uncommitted assembly files and unchanged table sources.',
        c_flags=FLAGS, renderer=False, statistics=False, lto=False,
        maximum_stack_bytes_by_call_graph=80,
        solver_early_return_stack_bytes=0,
        stack_call_graph={'_start':0, 'target_main':32, 'asm_parse':16,
                          'asm_solve':48, 'asm_replay':0},
        measurement_scope='Startup, parse, solve, replay, length check, exit ecall',
        sha256=hashes)
    (BUILD/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    (BUILD/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    (BUILD/'cases.json').write_text(json.dumps(summaries,indent=2)+'\n')
    print('ASM_V3_BUILD=PASS (Ripes execution is still required)')


if __name__ == '__main__':
    main()
