#!/usr/bin/env python3
"""Supplementary Ripes CLI checks of generated sources and new renderer.
GUI-source test defines LED symbols as ordinary RAM and disables the delay;
it checks assembly/execution, not an actual LED peripheral or GUI animation.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent.parent
BUILD=ROOT/'rv32/build/led'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ripes',type=Path,required=True)
    args=p.parse_args()
    cases=json.loads((BUILD/'cases.json').read_text())[:3]
    out=BUILD/'ripes-supplementary'
    out.mkdir(exist_ok=True)
    result=[]
    for case in cases:
        label=case['case']
        gui=(BUILD/(label+'-gui.s')).read_text()
        test='.equ LED_MATRIX_0_BASE, 0x200000\n.equ LED_MATRIX_0_WIDTH, 35\n.equ LED_MATRIX_0_HEIGHT, 25\n'
        test+=gui.replace('.equ LED_DELAY, 300000','.equ LED_DELAY, 0')
        # Honor any custom --delay selected during build, not just the default.
        test='\n'.join('.equ LED_DELAY, 0' if l.startswith('.equ LED_DELAY,') else l for l in test.splitlines())+'\n'
        test_path=out/(label+'-renderer-ram.s')
        test_path.write_text(test)
        for variant,source,kind in [('cli-elf',BUILD/(label+'-cli.elf'),'elf'),
                                    ('cli-source',BUILD/(label+'-cli.s'),'asm'),
                                    ('renderer-ram-source',test_path,'asm')]:
            report=out/(label+'-'+variant+'.json')
            report.unlink(missing_ok=True)
            cmd=[str(args.ripes.resolve()),'--mode','cli','--src',str(source.resolve()),
                 '-t',kind,'--proc','RV32_ISS','--timeout','30000','--iret','--regs',
                 '--runinfo','--json','--output',str(report.resolve())]
            run=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
            (out/(label+'-'+variant+'.log')).write_text(run.stdout)
            assert run.returncode==0 and report.is_file(),run.stdout
            data=json.loads(report.read_text())
            regs=data['registers']
            assert (regs['x25'],regs['x26'],regs['x27'])==(0x600d,0,case['expected_length'])
            if variant=='cli-elf':
                old=ROOT/'measurements/stage4-asm-v5/20261006T085548Z-RV32_ISS-051199'/(label+'.json')
                expected=json.loads(old.read_text())['# instructions retired']
                assert data['# instructions retired']==expected,(label,expected,data['# instructions retired'])
            result.append(dict(case=label,variant=variant,
                               source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                               retired_instructions=data['# instructions retired'],status=regs['x26'],
                               length=regs['x27'],command=cmd))
            print(label,variant,'PASS',data['# instructions retired'],flush=True)
    # An incorrectly configured device must fail before rendering, rather than
    # interpreting a wrong row stride and writing outside the matrix.
    negative=[]
    for width,height in [(34,25),(35,24)]:
        source=out/f'bad-size-{width}x{height}.s'
        gui=(BUILD/'solved-gui.s').read_text()
        source.write_text(f'.equ LED_MATRIX_0_BASE, 0x200000\n.equ LED_MATRIX_0_WIDTH, {width}\n.equ LED_MATRIX_0_HEIGHT, {height}\n'+gui)
        report=source.with_suffix('.json')
        report.unlink(missing_ok=True)
        cmd=[str(args.ripes.resolve()),'--mode','cli','--src',str(source.resolve()),'-t','asm',
             '--proc','RV32_ISS','--timeout','15000','--regs','--json','--output',str(report.resolve())]
        run=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=20)
        source.with_suffix('.log').write_text(run.stdout)
        # Ripes CLI may return the guest status as its process exit status.
        data=json.loads(report.read_text())
        assert data['registers']['x26']==5 and data['registers']['x25']==0x600d
        negative.append(dict(width=width,height=height,status=5,command=cmd))
    cmd=[str(args.ripes.resolve()),'--mode','cli','--src',str((BUILD/'solved-gui.s').resolve()),
         '-t','asm','--proc','RV32_ISS','--timeout','15000']
    run=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=20)
    (out/'no-peripheral-expected-failure.log').write_text(run.stdout)
    assert run.returncode!=0 and 'Error during assembly' in run.stdout
    summary=dict(status='PASS',processor='RV32_ISS',
                 ripes_sha256=hashlib.sha256(args.ripes.read_bytes()).hexdigest(),
                 scope='Supplementary Linux build 5b8a616; RAM symbols in renderer test; not Windows GUI proof',
                 cases=result,negative_dimension_checks=negative,
                 gui_without_peripheral_expected_assembly_failure=True,
                 actual_GUI_peripheral_verified=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':main()
