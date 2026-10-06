"""Test actual linking and checkpoint orchestration with a FAKE Ripes adapter.

All simulated reports live in a TemporaryDirectory and are deleted. They must
never be used as target measurements. Requires prepare.py and GNU RV32 tools.
"""
import argparse
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import common as c
spec = importlib.util.spec_from_file_location('gate_workflow',HERE/'run.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class WorkflowTests(unittest.TestCase):
    def test_real_linking_across_input_extremes(self):
        manifest = c.read(c.BUILD/'manifest.json')
        template = (c.BUILD/'template.elf').read_bytes()
        offset = manifest['cube_input_offset']
        objects = [c.BUILD/name for name in manifest['objects']]
        cases = c.load_cases()
        selected = [cases[0]['input'],cases[-1]['input'],'41532672313211','21345671111111']
        with tempfile.TemporaryDirectory() as tmp:
            for state in selected:
                with self.subTest(state=state):
                    elf,_ = c.build_case(state,Path(tmp),objects,template,offset)
                    self.assertEqual(elf.read_bytes()[offset:offset+15],state.encode()+b'\0')
                    # An unrelated byte change must fail the comparison.
                    broken = bytearray(template)
                    broken[0] ^= 1
                    with self.assertRaises(ValueError):
                        c.build_case(state,Path(tmp),objects,bytes(broken),offset)

    def test_pause_failure_resume_completion_and_reverify(self):
        with tempfile.TemporaryDirectory(prefix='FAKE-RIPES-TEST-') as tmp:
            root = Path(tmp)
            build = root/'build'
            build.mkdir()
            manifest = c.read(c.BUILD/'manifest.json')
            # Three cases only: this is a workflow test, not a target gate.
            cases = c.load_cases()[:3]
            for name in manifest['artifacts']:
                shutil.copy2(c.BUILD/name,build/name)
            c.atomic(build/'cases.json',cases)
            manifest['artifacts']['cases.json'] = c.sha(build/'cases.json')
            c.atomic(build/'manifest.json',manifest)
            fake_exe = root/'FAKE-Ripes.exe'
            fake_exe.write_text('Not executable. Test fixture only.')
            working_root = root/'windows'
            archives = root/'measurements'
            launches = []
            fail_next = [False]
            real_run, real_which = subprocess.run,shutil.which

            def fake_run(argv,*args,**kwargs):
                if argv[0] != 'powershell.exe':
                    return real_run(argv,*args,**kwargs)
                attempt_file = max(archives.glob('*/attempts/*.json'),key=lambda p:p.stat().st_mtime_ns)
                attempt = c.read(attempt_file)
                launches.append(attempt['rank'])
                if fail_next[0]:
                    fail_next[0] = False
                    return subprocess.CompletedProcess(argv,1,b'TEST ONLY: simulated launch failure')
                archive = attempt_file.parent.parent
                env = c.read(archive/'ripes-environment.json')
                report = c.read(c.REFERENCE/'distance11.json')
                report['runinfo']['source file'] = f"d11-{attempt['rank']:07d}.elf"
                report['# instructions retired'] = 12345  # Deliberately synthetic.
                c.atomic(working_root/env['run_id']/attempt['raw_report'],report)
                return subprocess.CompletedProcess(argv,0,b'TEST ONLY: fake Ripes output')

            def which(name):
                return name if name in ('powershell.exe','wslpath') else real_which(name)

            with ExitStack() as stack:
                for name,value in dict(ROOT=root,BUILD=build,RIPES=fake_exe,
                    RIPES_SHA=c.sha(fake_exe),RUN_ROOT=working_root,ARCHIVES=archives,
                    COUNT=3,load_cases=lambda:cases,winpath=lambda p:str(p)).items():
                    stack.enter_context(patch.object(r,name,value))
                stack.enter_context(patch.object(subprocess,'run',side_effect=fake_run))
                stack.enter_context(patch.object(shutil,'which',side_effect=which))
                stack.enter_context(redirect_stdout(StringIO()))
                args = argparse.Namespace(resume=None,new_run=False,max_new=1,verify_only=False)
                r.execute(args)
                archive = next(archives.iterdir())
                self.assertEqual(c.read(archive/'summary.json')['status'],'INCOMPLETE')
                self.assertEqual(c.read(archive/'summary.json')['passed_cases'],1)
                fail_next[0] = True
                args.max_new = None
                with self.assertRaises(ValueError): r.execute(args)
                self.assertEqual(c.read(archive/'ripes-environment.json')['status'],'FAILED')
                self.assertEqual(c.read(archive/'summary.json')['status'],'FAILED')
                self.assertEqual(len(list((archive/'results').glob('*.json'))),1)
                r.execute(args)
                self.assertEqual(c.read(archive/'summary.json')['status'],'PASS')
                self.assertEqual(c.read(archive/'summary.json')['passed_cases'],3)
                self.assertEqual(launches,[cases[0]['rank'],cases[1]['rank'],cases[1]['rank'],cases[2]['rank']])
                args.verify_only = True
                r.execute(args)
                args.verify_only = False
                r.execute(args)
                self.assertEqual(len(launches),4,'Completed runs must not launch Ripes again')
                self.assertEqual(len(list((archive/'attempts').glob('*.json'))),4,'Failed attempt must remain')


if __name__ == '__main__': unittest.main(verbosity=2)
