#!/usr/bin/env python3
"""Measure every distance-11 state in pinned Windows Ripes; resume by default."""
import argparse
import datetime
import fcntl
import shutil
import statistics
import subprocess
import time
import uuid
from common import *

RIPES = Path('/mnt/c/Tools/Ripes/Ripes.exe')
RUN_ROOT = Path('/mnt/c/Tools/Ripes/hw1_stage4_distance11')
ARCHIVES = ROOT/'measurements/stage4-asm-v5-distance11'


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def winpath(path):
    return subprocess.check_output(['wslpath','-w',str(path)],text=True).strip()


def ps_quote(text):
    return "'"+text.replace("'", "''")+"'"


def result_row(case, iret, raw, elf_hash, attempt):
    return dict(rank=case['rank'], input=case['input'], processor='RV32_ISS',
                length=11, status=0, retired_instructions=iret,
                text_bytes=1428, static_data_bytes=126488,
                elf_sha256=elf_hash, raw_report=raw.name, raw_sha256=sha(raw),
                attempt=attempt, completed_at=now())


def load_results(archive, cases, template, offset):
    """Only immutable per-case success records backed by valid raw output count."""
    index = {c['rank']:c for c in cases}
    results = {}
    for path in sorted((archive/'results').glob('*.json')):
        row = read(path)
        rank = row['rank']
        require(rank in index and rank not in results and path.name == f'{rank:07d}.json',
                'Unexpected/duplicate result rank')
        case = index[rank]
        require(row['input'] == case['input'] and row['processor'] == 'RV32_ISS' and
                row['length'] == 11 and row['status'] == 0 and
                row['text_bytes'] == 1428 and row['static_data_bytes'] == 126488,
                'Result metadata mismatch')
        require(Path(row['raw_report']).name == row['raw_report'], 'Invalid report filename')
        raw = archive/'raw'/row['raw_report']
        require(sha(raw) == row['raw_sha256'], 'Raw report changed: '+str(raw))
        iret = validate_report(read(raw), f'd11-{rank:07d}.elf')
        require(iret == row['retired_instructions'], 'Result count differs from raw output')
        require(row['elf_sha256'] == digest(expected_elf(template,offset,case['input'])),
                'Result ELF hash does not match its input and audited template')
        attempt = read(archive/'attempts'/(row['attempt']+'.json'))
        require(attempt['rank'] == rank and attempt['input'] == case['input'] and
                attempt['elf_sha256'] == row['elf_sha256'] and attempt['returncode'] == 0 and
                attempt['raw_report'] == row['raw_report'] and attempt['raw_sha256'] == row['raw_sha256'],
                'Attempt provenance mismatch')
        require(sha(archive/'attempts'/(row['attempt']+'.input.S')) == attempt['input_source_sha256'],
                'Input assembly evidence changed')
        require((archive/'attempts'/(row['attempt']+'.input.S')).read_text() == input_source(case['input']),
                'Input assembly evidence does not encode the recorded state')
        results[rank] = row
    return results


def write_summary(archive, results, status_override=None):
    fields = ['rank','input','processor','length','status','retired_instructions',
              'text_bytes','static_data_bytes','elf_sha256','raw_report']
    temp = archive/'summary.csv.tmp'
    with temp.open('w',newline='') as f:
        writer = csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        writer.writeheader()
        writer.writerows(results[k] for k in sorted(results))
    temp.replace(archive/'summary.csv')
    values = list(results.values())
    worst = max(values,key=lambda r:r['retired_instructions']) if values else None
    summary = dict(status=status_override or ('PASS' if len(values) == COUNT else 'INCOMPLETE'),
                   expected_cases=COUNT, passed_cases=len(values), instruction_limit=LIMIT,
                   processor='RV32_ISS', renderer=False,
                   text_bytes=1428, static_data_bytes=126488,
                   minimum_retired_instructions=min((r['retired_instructions'] for r in values),default=None),
                   mean_retired_instructions=statistics.mean(r['retired_instructions'] for r in values) if values else None,
                   maximum_retired_instructions=worst['retired_instructions'] if worst else None,
                   worst_input=worst['input'] if worst else None,
                   note='Full gate PASS requires all 2,644 exact BFS distance-11 states; partial results are not PASS.')
    atomic(archive/'summary.json',summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume', type=Path, help='Explicit existing evidence directory; default resumes the active run')
    parser.add_argument('--new-run', action='store_true', help='Start a separate measurement archive')
    parser.add_argument('--max-new', type=int, help='Stop cleanly after this many additional cases; default all remaining')
    parser.add_argument('--verify-only', action='store_true', help='Validate archived evidence without launching Ripes')
    args = parser.parse_args()
    require(not (args.resume and args.new_run), '--resume and --new-run are mutually exclusive')
    require(args.max_new is None or args.max_new > 0, '--max-new must be positive')
    require(not (args.verify_only and args.new_run), '--verify-only cannot start a new run')
    require((BUILD/'manifest.json').is_file(), 'Run python3 rv32/distance11/prepare.py first')
    with (BUILD/'lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        execute(args)


def execute(args):
    manifest = read(BUILD/'manifest.json')
    check_sources(manifest)
    for name, value in manifest['artifacts'].items():
        require(sha(BUILD/name) == value, 'Prepared artifact changed: '+name)
    cases = read(BUILD/'cases.json')
    require(cases == load_cases(), 'Prepared case list changed')
    template = (BUILD/'template.elf').read_bytes()
    offset = manifest['cube_input_offset']
    active = BUILD/'active-run.json'
    if args.resume:
        archive = args.resume.resolve()
    elif active.exists() and not args.new_run:
        archive = ROOT/read(active)['archive']
    else:
        require(not args.verify_only, 'No active run to verify')
        archive = None

    if not args.verify_only:
        for tool in ('powershell.exe','wslpath',PREFIX+'gcc'):
            require(shutil.which(tool), 'Run inside WSL; missing '+tool)
        require(RIPES.is_file() and sha(RIPES) == RIPES_SHA, 'Pinned Ripes executable is missing or differs')
        gcc = subprocess.check_output([PREFIX+'gcc','--version'],text=True).splitlines()[0]
        linker = subprocess.check_output([PREFIX+'ld','--version'],text=True).splitlines()[0]
        require(gcc == manifest['gcc'] and linker == manifest['linker'], 'Toolchain changed since preparation')

    if archive is None:
        run_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-RV32_ISS-'+uuid.uuid4().hex[:6]
        archive = ARCHIVES/run_id
        archive.mkdir(parents=True,exist_ok=False)
        for folder in ('results','raw','attempts','build'):
            (archive/folder).mkdir()
        for name in ['manifest.json', *manifest['artifacts']]:
            # Object files are reproducible; retain one complete audited ELF plus build recipes.
            if not name.endswith('.o'):
                shutil.copy2(BUILD/name,archive/'build'/name)
        environment = dict(schema=1, variant='asm-v5', created_at=now(), status='INCOMPLETE',
            processor='RV32_ISS', ripes_sha256=RIPES_SHA,
            pinned_ripes_version='v2.2.6-106-g5b8a616', ripes_executable=winpath(RIPES),
            renderer=False, statistics=False, instruction_limit=LIMIT, expected_cases=COUNT,
            measurement_scope=manifest['measurement_scope'],
            windows_working_directory=winpath(RUN_ROOT/run_id), run_id=run_id,
            manifest_sha256=sha(BUILD/'manifest.json'), sessions=[])
        atomic(archive/'ripes-environment.json',environment)
        atomic(active,dict(archive=str(archive.relative_to(ROOT))))
    require(archive.is_dir(), 'Resume archive is missing')
    environment = read(archive/'ripes-environment.json')
    require(environment['manifest_sha256'] == sha(BUILD/'manifest.json') and
            environment['processor'] == 'RV32_ISS' and environment['ripes_sha256'] == RIPES_SHA and
            environment['renderer'] is False and environment['instruction_limit'] == LIMIT and
            environment['expected_cases'] == COUNT, 'Archive/build configuration mismatch')
    require(sha(archive/'build/manifest.json') == environment['manifest_sha256'], 'Archived manifest changed')
    for name,value in manifest['artifacts'].items():
        if not name.endswith('.o'):
            require(sha(archive/'build'/name) == value, 'Archived build artifact changed: '+name)
    results = load_results(archive,cases,template,offset)
    print(f'Checked {len(results)}/{COUNT} existing passing cases. Evidence: {archive.relative_to(ROOT)}',flush=True)
    if args.verify_only:
        summary = write_summary(archive,results)
        print('DISTANCE11_EVIDENCE='+summary['status'])
        return
    if len(results) == COUNT:
        summary = write_summary(archive,results)
        environment['status'] = 'PASS'
        atomic(archive/'ripes-environment.json',environment)
        print('ASM_V5_DISTANCE11_GATE=PASS (verified existing complete run; no cases rerun)')
        return
    working = RUN_ROOT/environment['run_id']
    working.mkdir(parents=True,exist_ok=True)
    require(winpath(working) == environment['windows_working_directory'], 'Working directory changed')
    environment['sessions'].append(dict(started_at=now(),prior_passes=len(results),max_new=args.max_new))
    environment['status'] = 'INCOMPLETE'
    atomic(archive/'ripes-environment.json',environment)
    objects = [BUILD/name for name in manifest['objects']]
    new = 0
    started = time.monotonic()
    try:
        for case in cases:
            if case['rank'] in results:
                continue
            if args.max_new is not None and new >= args.max_new:
                break
            rank = case['rank']
            elf, commands = build_case(case['input'],BUILD/'link',objects,template,offset)
            filename = f'd11-{rank:07d}.elf'
            shutil.copy2(elf,working/filename)
            expected_hash = sha(elf)
            require(sha(working/filename) == expected_hash, 'Windows ELF copy differs')
            attempt_id = f'{rank:07d}-'+uuid.uuid4().hex[:12]
            report_name = attempt_id+'.json'
            raw = archive/'raw'/report_name
            assembly = archive/'attempts'/(attempt_id+'.input.S')
            shutil.copy2(BUILD/'link/input.S',assembly)
            arguments = (f'--mode cli --src {filename} -t elf --proc RV32_ISS '
                         f'--timeout 120000 --iret --regs --runinfo --exectime --json --output {report_name}')
            command = ("$ErrorActionPreference = 'Stop'; $p = Start-Process -FilePath "+ps_quote(winpath(RIPES))+
                       ' -WorkingDirectory '+ps_quote(winpath(working))+' -ArgumentList '+ps_quote(arguments)+
                       ' -PassThru -Wait; exit $p.ExitCode')
            attempt = dict(rank=rank,input=case['input'],started_at=now(),elf_sha256=expected_hash,
                input_source_sha256=sha(assembly),build_commands=commands,command=command,
                raw_report=report_name,returncode=None)
            attempt_file = archive/'attempts'/(attempt_id+'.json')
            atomic(attempt_file,attempt)
            try:
                proc = subprocess.run(['powershell.exe','-NoProfile','-Command',command],
                    stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=150)
                (archive/'attempts'/(attempt_id+'.launch.log')).write_bytes(proc.stdout)
                attempt['returncode'] = proc.returncode
                if (working/report_name).exists():
                    shutil.copy2(working/report_name,raw)
                    attempt['raw_sha256'] = sha(raw)
                attempt['finished_at'] = now()
                atomic(attempt_file,attempt)
                require(proc.returncode == 0 and raw.is_file(),
                        'Ripes launch/execution failed. Inspect '+str(attempt_file))
                iret = validate_report(read(raw),filename)
                row = result_row(case,iret,raw,expected_hash,attempt_id)
                atomic(archive/'results'/f'{rank:07d}.json',row)
                results[rank] = row
                new += 1
                if new <= 3 or len(results) % 25 == 0 or len(results) == COUNT:
                    seconds = time.monotonic()-started
                    remaining = seconds/new*(COUNT-len(results))/60
                    print(f"PASS {len(results)}/{COUNT}: {case['input']} iret={iret:,}; estimated remaining {remaining:.1f} min",flush=True)
                    write_summary(archive,results)
                (working/filename).unlink()
            except BaseException as exc:
                # Preserve partial output even when the outer launch watchdog fires.
                if isinstance(exc,subprocess.TimeoutExpired):
                    (archive/'attempts'/(attempt_id+'.launch.log')).write_bytes(exc.output or b'')
                if not raw.exists() and (working/report_name).exists():
                    shutil.copy2(working/report_name,raw)
                    attempt['raw_sha256'] = sha(raw)
                attempt['error'] = type(exc).__name__+': '+str(exc)
                atomic(attempt_file,attempt)
                raise
        check_sources(manifest)
        require(sha(RIPES) == RIPES_SHA, 'Ripes changed during measurement')
        results = load_results(archive,cases,template,offset)
        summary = write_summary(archive,results)
        environment['status'] = summary['status']
        environment['sessions'][-1]['finished_at'] = now()
        environment['sessions'][-1]['new_passes'] = new
        atomic(archive/'ripes-environment.json',environment)
        print('ASM_V5_DISTANCE11_GATE='+summary['status'])
        print(f"Passed {len(results)}/{COUNT}; max iret={summary['maximum_retired_instructions']}; worst={summary['worst_input']}")
        print('Evidence: '+str(archive.relative_to(ROOT)))
        if len(results) != COUNT:
            print('Resume with the same command (omit --max-new to finish all remaining cases).')
    except BaseException as exc:
        environment['status'] = 'INCOMPLETE' if isinstance(exc,KeyboardInterrupt) else 'FAILED'
        environment['sessions'][-1]['error'] = type(exc).__name__+': '+str(exc)
        environment['sessions'][-1]['finished_at'] = now()
        atomic(archive/'ripes-environment.json',environment)
        write_summary(archive,results,status_override=environment['status'])
        print('Run stopped; passing cases and failed-attempt evidence are preserved. Resume with the same command.',flush=True)
        raise


if __name__ == '__main__':
    main()
