"""Host-only regression tests; temporary fixtures are NOT target measurements."""
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import common as c
spec = importlib.util.spec_from_file_location('gate_runner',HERE/'run.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.report = c.read(c.REFERENCE/'distance11.json')

    def test_archived_output(self):
        self.assertEqual(c.validate_report(self.report,'distance11.elf'),1468209)

    def test_reject_bad_target_and_telemetry(self):
        for key,value in [('x25',0),('x26',1),('x27',10),('x17',0)]:
            report = copy.deepcopy(self.report)
            report['registers'][key] = value
            with self.assertRaises(ValueError): c.validate_report(report,'distance11.elf')
        for count in (0,-1,50_000_001,True,'1468209'):
            report = copy.deepcopy(self.report)
            report['# instructions retired'] = count
            with self.assertRaises(ValueError): c.validate_report(report,'distance11.elf')
        for key,value in [('processor','RV32_5S'),('ISA extensions',['M']),('source file','other.elf')]:
            report = copy.deepcopy(self.report)
            report['runinfo'][key] = value
            with self.assertRaises(ValueError): c.validate_report(report,'distance11.elf')
        report = copy.deepcopy(self.report)
        del report['runinfo']
        with self.assertRaises(ValueError): c.validate_report(report,'distance11.elf')

    def test_budget_inclusive(self):
        self.report['# instructions retired'] = 50_000_000
        self.assertEqual(c.validate_report(self.report,'distance11.elf'),50_000_000)


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.archive = Path(self.tmp.name)
        for name in ('raw','results','attempts'): (self.archive/name).mkdir()
        self.cases = c.load_cases()
        self.case = self.cases[0]
        self.template = b'test prefix'+b'21345671111111\0'+b'test suffix'
        self.offset = len(b'test prefix')
        rank = self.case['rank']
        self.attempt = 'test-attempt'
        raw = self.archive/'raw/test.json'
        report = c.read(c.REFERENCE/'distance11.json')
        report['runinfo']['source file'] = f'd11-{rank:07d}.elf'
        c.atomic(raw,report)
        elf_hash = c.digest(c.expected_elf(self.template,self.offset,self.case['input']))
        self.row = r.result_row(self.case,1468209,raw,elf_hash,self.attempt)
        source = self.archive/'attempts/test-attempt.input.S'
        source.write_text(c.input_source(self.case['input']))
        c.atomic(self.archive/'attempts/test-attempt.json',dict(rank=rank,input=self.case['input'],
            elf_sha256=elf_hash,returncode=0,raw_report=raw.name,raw_sha256=c.sha(raw),input_source_sha256=c.sha(source)))
        self.result_path = self.archive/'results'/f'{rank:07d}.json'

    def tearDown(self): self.tmp.cleanup()

    def load(self):
        return r.load_results(self.archive,self.cases,self.template,self.offset)

    def test_resume_uses_only_verified_success(self):
        self.assertEqual(self.load(),{})  # Raw output alone is not a checkpoint.
        c.atomic(self.result_path,self.row)
        results = self.load()
        self.assertEqual(list(results),[self.case['rank']])
        self.assertEqual(r.write_summary(self.archive,results)['status'],'INCOMPLETE')
        self.assertEqual(len([x for x in self.cases if x['rank'] not in results]),2643)
        (self.archive/'results/interrupted.json.tmp').write_text('{')
        self.assertEqual(self.load(),results)  # Atomic-write debris is never counted.

    def test_raw_tampering_rejected(self):
        c.atomic(self.result_path,self.row)
        (self.archive/'raw/test.json').write_text('{}')
        with self.assertRaises(ValueError): self.load()

    def test_elf_or_input_mismatch_rejected(self):
        for field,value in [('elf_sha256','0'*64),('input','12345671111111'),('retired_instructions',1)]:
            row = dict(self.row,**{field:value})
            c.atomic(self.result_path,row)
            with self.assertRaises(ValueError): self.load()

    def test_failed_attempt_not_accepted(self):
        c.atomic(self.result_path,self.row)
        path = self.archive/'attempts/test-attempt.json'
        attempt = c.read(path)
        attempt['returncode'] = 1
        c.atomic(path,attempt)
        with self.assertRaises(ValueError): self.load()

    def test_duplicate_or_unknown_file_rejected(self):
        c.atomic(self.result_path,self.row)
        c.atomic(self.archive/'results/duplicate.json',self.row)
        with self.assertRaises(ValueError): self.load()


if __name__ == '__main__': unittest.main(verbosity=2)
