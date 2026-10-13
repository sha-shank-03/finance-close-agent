"""Injected dispatch failures and public projection; no native actor execution."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.u2c_progress import execute_slots,read_progress,counts,atomic_write
from evaluation.u2b_run import summary
from evaluation.u2c_summary import export,validate_bundle,build,validate,STRATA,POLICIES

ROOT=Path(__file__).resolve().parent.parent

def plan(out,n=2):
    return [{'slot_id':str(i),'case_id':'D11','policy':'scripted','stratum':'exact','run':str(out/str(i)),'argv':['NEVER-LAUNCH'],'gold_counts':{'matches':0,'holds':1,'proposals':0,'material':1}} for i in range(n)]

def scored():
    return {'passed':True,'raw_exact_state_success':True,'resolved_completion':False,'correct_handoff':True,'unsafe_committed':False,'human_handoff_present':True,'model_calls':0,'metrics':{'matches':{'tp':0,'predicted':0,'gold':0},'holds':{'tp':1,'predicted':1,'gold':1},'proposals':{'tp':0,'predicted':0,'gold':0},'material':{'gold':1,'missed':0}}}

def finish(command,**kwargs):
    kwargs['on_launched'](123);return subprocess.CompletedProcess(command,0,b'fictional',b'')

def fake_report(split):
    rows=[];prefix='D' if split=='dev' else 'C'
    for s,stratum in enumerate(STRATA,1):
        for variant in [1,2]:
            for policy in POLICIES:
                result=scored();result.update(actual_cost=None,checks=[{'name':'all cases complete exactly once','passed':True},{'name':'run genuinely packet ready','passed':True}],failures=[])
                for m in ['matches','holds','proposals']:result['metrics'][m]['unexpected']=[]
                rows.append({'case_id':prefix+str(s)+str(variant),'stratum':stratum,'policy':policy,'exit_code':0,'score':result,'gold_counts':{'matches':0,'holds':1,'proposals':0,'material':1},'elapsed_seconds':1.0,'argv':['C:'+'/'+'Users'+'/private/NOT-PUBLIC'],'private_source':'should disappear'})
    return {'schema_version':1,'split':split,'unique_tasks':16,'attempts':32,'repetitions':1,'author_exposed':True,'manifest_sha256':'a'*64,'manifest_unchanged':True,'code_sha256':{'evaluation/u2b_run.py':'b'*64},'code_unchanged':True,'batch_complete':True,'rows':rows}

class PureU2c(unittest.TestCase):
    def execute(self,out,**kwargs):return execute_slots(plan(out),out,metadata={'fictional':True},oracle=lambda row:scored(),**kwargs)

    def test_all_intended_and_STARTED_exist_before_dispatch(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);seen=[]
            def dispatch(command,**kwargs):
                intention=json.loads((out/'intended.json').read_text());self.assertEqual(2,len(intention['slots']))
                ledger=[json.loads(line) for line in (out/'dispatch-events.jsonl').read_text().splitlines()]
                self.assertEqual('STARTED',ledger[-1]['entry']['state'])
                self.assertEqual(2,read_progress(out)['counts']['planned']);seen.append(True)
                return finish(command,**kwargs)
            rows,progress=self.execute(out,dispatch=dispatch)
            self.assertEqual(2,len(seen));self.assertEqual(2,progress['counts']['dispatched']);self.assertEqual(2,progress['counts']['terminal'])
            self.assertEqual(rows,read_progress(out)['rows'])

    def test_deadline_unexecuted_is_never_attempted_or_zero_latency(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);clock=iter([0,180,180,180])
            rows,p=self.execute(out,dispatch=lambda *a,**k:self.fail('dispatch after deadline'),clock=lambda:next(clock))
            self.assertEqual(2,p['counts']['deadline_unexecuted']);self.assertEqual(0,summary(rows)['attempted'])
            self.assertEqual(2,summary(rows)['material']['missed']);self.assertIsNone(summary(rows)['unsafe_committed']['value'])
            self.assertEqual(0,summary(rows)['latency_seconds']['observed_attempts']);self.assertTrue(all(r['exit_code'] is None and 'elapsed_seconds' not in r for r in rows))

    def test_interrupt_before_launch_is_dispatch_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)
            def interrupt(*a,**k):raise KeyboardInterrupt()
            rows,p=self.execute(out,dispatch=interrupt)
            self.assertEqual(1,p['counts']['interrupted_unknown']);self.assertEqual(1,p['counts']['dispatch_unknown']);self.assertEqual(1,p['counts']['pending_unexecuted']);self.assertEqual(0,p['counts']['dispatched'])
            self.assertIsNone(rows[0]['exit_code']);self.assertEqual(2,summary(rows)['unsafe_committed']['unknown_attempts'])

    def test_deadline_after_START_marker_still_never_dispatches(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);clock=iter([0,0,0,180,180,180])
            rows,p=self.execute(out,dispatch=lambda *a,**k:self.fail('late launch'),clock=lambda:next(clock))
            self.assertEqual(1,p['counts']['dispatch_started']);self.assertEqual(0,p['counts']['dispatched']);self.assertEqual(2,p['counts']['deadline_unexecuted'])
            self.assertTrue(all(r['exit_code'] is None and 'elapsed_seconds' not in r for r in rows))

    def test_lost_confirmed_child_result_stays_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)
            def interrupt(command,**kwargs):kwargs['on_launched'](123);raise KeyboardInterrupt()
            rows,p=self.execute(out,dispatch=interrupt)
            self.assertEqual(1,p['counts']['dispatched']);self.assertEqual(0,p['counts']['terminal']);self.assertIsNone(rows[0]['score']);self.assertIsNone(rows[0]['exit_code'])
            self.assertEqual(0,summary(rows)['latency_seconds']['observed_attempts']);self.assertFalse(read_progress(out)['redispatch_permitted'])

    def test_launch_error_terminal_has_no_native_exit_or_latency(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)
            def error(*a,**k):raise OSError('fictional launch failure')
            rows,p=self.execute(out,dispatch=error)
            self.assertEqual(2,p['counts']['terminal']);self.assertEqual(0,p['counts']['dispatched']);self.assertEqual(2,summary(rows)['execution_errors']);self.assertEqual(2,summary(rows)['material']['missed'])
            self.assertTrue(all(r['exit_code'] is None and 'elapsed_seconds' not in r and r['actual_cost'] is None for r in rows))

    def test_nonzero_native_and_oracle_error_preserve_denominators(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)
            def error(command,**kwargs):kwargs['on_launched'](123);return subprocess.CompletedProcess(command,4,b'',b'')
            def oracle(row):raise ValueError('fictional bad state')
            rows,p=execute_slots(plan(out),out,metadata={},dispatch=error,oracle=oracle)
            self.assertEqual(2,p['counts']['terminal']);self.assertEqual(2,summary(rows)['execution_errors']);self.assertEqual(2,summary(rows)['material']['missed']);self.assertIsNone(summary(rows)['model_calls'])

    def test_parent_dies_before_marker_recovery_is_readonly(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)
            self.execute(out,dispatch=lambda *a,**k:(_ for _ in ()).throw(KeyboardInterrupt()))
            events=out/'dispatch-events.jsonl';lines=events.read_bytes().splitlines(keepends=True);events.write_bytes(lines[0]+b'{partial')
            before=events.read_bytes();recovered=read_progress(out)
            self.assertEqual(1,recovered['counts']['interrupted_unknown']);self.assertTrue(recovered['partial_journal_tail']);self.assertEqual(before,events.read_bytes())

    def test_START_marker_storage_failure_never_calls_dispatch(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);real=atomic_write;calls=[]
            def fail(path,value):
                if Path(path).name=='case-results.json' and any(r['state']=='STARTED' for r in value):raise OSError('injected checkpoint write')
                return real(path,value)
            with patch('evaluation.u2c_progress.atomic_write',side_effect=fail):
                rows,p=self.execute(out,dispatch=lambda *a,**k:calls.append(True))
            self.assertEqual([],calls);self.assertEqual(0,p['counts']['dispatched']);self.assertEqual(2,p['counts']['terminal'])

    def test_no_native_default_dispatch_in_pure_checks(self):
        with self.assertRaises(AssertionError):
            from evaluation.u2c_progress import native_dispatch
            with patch('subprocess.Popen',side_effect=AssertionError('blocked')):native_dispatch(['DO-NOT-LAUNCH'],cwd=None,timeout=1,on_launched=lambda pid:None)

    def test_public_export_omits_private_fields_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);dev=base/'dev.json';cap=base/'cap.json';out=base/'public'
            dev.write_text(json.dumps(fake_report('dev')));cap.write_text(json.dumps(fake_report('capability')))
            export(dev,cap,out);self.assertTrue(validate_bundle(out));self.assertNotIn('private',(out/'summary.json').read_text())
            with self.assertRaises(ValueError):export(dev,cap,out)

    def test_public_validator_rejects_repinned_forgery_and_private_paths(self):
        value=build(fake_report('dev'),fake_report('capability'),'c'*64,'d'*64)
        for change in ['count','quality','cost','path']:
            altered=copy.deepcopy(value)
            if change=='count':altered['dispatched']=63
            elif change=='quality':altered['quality']['dev']['scripted']['raw_exact_state_success']=15
            elif change=='cost':altered['actual_measured_cost']=0
            else:altered['splits'][0]['rows'][0]['argv']=['private']
            with self.assertRaises(ValueError):validate(altered)

    def test_C81_extra_hold_is_preserved_as_quality_failure(self):
        cap=fake_report('capability')
        for row in cap['rows']:
            if row['case_id']=='C81':
                s=row['score'];s.update(passed=False,raw_exact_state_success=False,correct_handoff=False)
                s['failures']=[{'name':'exact independently labeled holds'}];s['metrics']['holds']['predicted']=2;s['metrics']['holds']['unexpected']=[['fictional',None,'INCOMPLETE_HISTORY',40700]]
        value=build(fake_report('dev'),cap,'c'*64,'d'*64)
        self.assertEqual(15,value['quality']['capability']['scripted']['raw_exact_state_success']);self.assertEqual(32,value['paired']['ties']);self.assertEqual(64,value['terminal'])

if __name__=='__main__':unittest.main()
