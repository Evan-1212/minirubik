#!/usr/bin/env python3
"""Prepare one audited asm-v5 object set and the full fixed distance-11 list."""
import datetime
import platform
import shutil
import subprocess
import sys
from common import *


def main():
    import fcntl
    BUILD.mkdir(parents=True, exist_ok=True)
    with (BUILD/'lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (BUILD/'manifest.json').exists():
            manifest = read(BUILD/'manifest.json')
            check_sources(manifest)
            for name, value in manifest['artifacts'].items():
                require(sha(BUILD/name) == value, 'Prepared artifact changed: '+name)
            print('DISTANCE11_PREPARE=PASS (reused matching prepared build)')
            return
        sources = source_hashes()
        cases = load_cases()
        for tool in ('cc', PREFIX+'gcc', PREFIX+'ld', PREFIX+'readelf', PREFIX+'objdump', PREFIX+'nm'):
            require(shutil.which(tool), 'Missing tool: '+tool)
        commands = []
        def run(command):
            commands.append(command)
            return subprocess.check_output(command, cwd=ROOT, stderr=subprocess.STDOUT, text=True)
        print('Checking all 2,644 states against the independent BFS shell...', flush=True)
        run(['cc','-O2',str(HERE/'oracle_list.c'),'-o',str(BUILD/'oracle-list')])
        output = run([str(BUILD/'oracle-list')])
        require(output.splitlines() == [f"{c['rank']},{c['input']}" for c in cases],
                'Archived case list differs from the complete independent BFS shell')
        (BUILD/'oracle-list.csv').write_text(output)
        sys.path.insert(0, str(ROOT/'rv32/asm_v5'))
        import build as v5
        objects = []
        print('Compiling the unchanged asm-v5 runtime once for the full gate...', flush=True)
        for source in v5.TABLES + v5.ASM:
            obj = BUILD/(source.replace('/','_')+'.o')
            flags = v5.FLAGS if source.endswith('.c') else ['-march=rv32i','-mabi=ilp32']
            run([PREFIX+'gcc', *flags, '-c', str(ROOT/source), '-o', str(obj)])
            objects.append(obj)
        elf, link_commands = build_case('21345671111111', BUILD/'link', objects)
        commands.extend(link_commands)
        shutil.copy2(elf, BUILD/'template.elf')
        shutil.copy2(elf.with_suffix('.map'), BUILD/'template.map')
        shutil.copy2(BUILD/'link/input.S', BUILD/'template-input.S')
        from inspect_elf import inspect
        audit = inspect(BUILD/'template.elf')
        require(audit['text_bytes'] == 1428 and audit['static_data_bytes'] == 126488,
                'Unexpected text or static data size')
        old = next(c for c in read(REFERENCE/'cases.json') if c['case'] == 'distance11')
        require(sha(BUILD/'template.elf') == old['elf_sha256'],
                'Template is not byte-identical to the locally measured asm-v5 ELF; inspect toolchain before continuing')
        offset = symbol_file_offset(BUILD/'template.elf', 'cube_input')
        require((BUILD/'template.elf').read_bytes()[offset:offset+15] == b'21345671111111\0', 'Bad input offset')
        atomic(BUILD/'cases.json', cases)
        atomic(BUILD/'commands.json', commands)
        artifacts = [*objects, BUILD/'template.elf', BUILD/'template.map', BUILD/'template-input.S',
                     BUILD/'template.audit.json', BUILD/'template.sections.txt', BUILD/'template.symbols.txt',
                     BUILD/'template.disasm.txt', BUILD/'cases.json', BUILD/'oracle-list.csv', BUILD/'commands.json']
        manifest = dict(schema=1, variant='asm-v5', base_commit=BASE_COMMIT,
            prepared_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            source_commit=run(['git','rev-parse','HEAD']).strip(),
            platform=platform.platform(), gcc=run([PREFIX+'gcc','--version']).splitlines()[0],
            linker=run([PREFIX+'ld','--version']).splitlines()[0],
            host_cc=run(['cc','--version']).splitlines()[0],
            case_count=COUNT, exact_bfs_shell_matches=True, instruction_limit=LIMIT,
            renderer=False, measurement_scope='Startup, parse, solve, replay, length check, exit ecall',
            text_bytes=1428, static_data_bytes=126488, reserved_stack_bytes=4096,
            cube_input_offset=offset, template_matches_archived_v5=True,
            objects=[p.name for p in objects], sources=sources,
            artifacts={p.name:sha(p) for p in artifacts})
        atomic(BUILD/'manifest.json', manifest)
        print('DISTANCE11_PREPARE=PASS (2,644 exact states; template matches archived v5 byte for byte)')
        print('No new Ripes measurements have been made yet.')


if __name__ == '__main__':
    main()
