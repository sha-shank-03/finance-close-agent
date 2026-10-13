"""Prepared native process-accounting controls; requires a fresh local lease."""
import argparse
import json
import sys
import time
from pathlib import Path
from .u2c_progress import execute_slots,native_dispatch,read_progress,atomic_write
from .u2b_run import summary

def controls(out):
    out=Path(out)
    if out.exists():raise ValueError('Fresh process-contract output required')
    out.mkdir(parents=True);checks=[]
    for kind in ['success','nonzero','timeout','launch-error','lost-result','deadline-unexecuted']:
        root=out/kind;root.mkdir()
        program='import time;time.sleep(10)' if kind=='timeout' else 'raise SystemExit(4)' if kind=='nonzero' else 'print("fictional control")'
        slots=[{'slot_id':'native-control','case_id':'CONTROL','policy':'offline-contract','stratum':'process','run':str(root/'run'),'argv':[sys.executable,'-c',program],'gold_counts':{'matches':0,'holds':0,'proposals':0,'material':0}}]
        observed=[]
        def dispatch(command,**kwargs):
            # Validate that durable STARTED precedes any actual launch.
            state=json.loads((root/'case-results.json').read_text())[0]['state'];observed.append(state=='STARTED')
            if kind=='launch-error':raise OSError('Injected launch failure; no child')
            if kind=='timeout':kwargs['timeout']=.25
            result=native_dispatch(command,**kwargs)
            if kind=='lost-result':raise KeyboardInterrupt('Injected parent result loss after retained child cleanup')
            return result
        rows,p=execute_slots(slots,root,metadata={'mode':'native-process-double','domain_actor_executed':False},dispatch=dispatch,oracle=lambda row:None,max_seconds=0 if kind=='deadline-unexecuted' else 20)
        recovered=read_progress(root);c=p['counts'];r=rows[0]
        expected= r['state']=='TERMINAL' and r['exit_code']==0 if kind=='success' else r['state']=='TERMINAL' and r['exit_code']==4 if kind=='nonzero' else r['state']=='TERMINAL' and r.get('error_class')=='task_deadline' if kind=='timeout' else c['dispatched']==0 and r['state']=='TERMINAL' and r['exit_code'] is None if kind=='launch-error' else c['interrupted_unknown']==1 and c['dispatched']==1 and r['exit_code'] is None and r['score'] is None if kind=='lost-result' else c['deadline_unexecuted']==1 and c['dispatched']==0 and 'elapsed_seconds' not in r
        passed=expected and all(observed) and recovered['counts']==c
        checks.append({'control':kind,'passed':passed,'counts':c,'summary':summary(rows),'domain_actor_executed':False})
    result={'schema_version':1,'passed':all(c['passed'] for c in checks),'checks':checks,'model_calls':0,'external_calls':0,'native_domain_corpus_executed':False,'cleanup':'Retained native_dispatch children kill/join on timeout/error. Outer lease observer verifies identities and observes resource gaps.'}
    atomic_write(out/'receipt.json',result);return result['passed']

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True);args=p.parse_args(argv)
    try:passed=controls(args.out)
    except Exception:print(json.dumps({'passed':False,'error_class':'process_contract_failed'}));return 1
    print(json.dumps({'passed':passed,'controls':6,'domain_actor_executed':False}));return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
