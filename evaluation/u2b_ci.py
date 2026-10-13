"""Offline report package checks; does not repeat corpus/native executions."""
import argparse
import json
from pathlib import Path
from .u2b_run import frozen
from .u2c_progress import read_progress,counts


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dev-report',required=True);p.add_argument('--capability-report',required=True);p.add_argument('--out',required=True)
    args=p.parse_args(argv);out=Path(args.out)
    if out.exists():raise ValueError('Fresh CI receipt output required')
    out.mkdir(parents=True);_,pin=frozen();checks=[]
    for split,name in [('dev',args.dev_report),('capability',args.capability_report)]:
        report=json.loads(Path(name).read_text(encoding='utf-8'))
        progress=read_progress(Path(name).parent)
        passed=report['schema_version']==2 and report['split']==split and report['unique_tasks']==16 and report['planned_slots']==32 and report['manifest_sha256']==pin and report['manifest_unchanged'] and report['code_unchanged'] and report['batch_complete'] and not progress['partial_journal_tail'] and progress['rows']==report['rows'] and counts(progress['rows'])==report['progress']['counts'] and progress['counts']['terminal']==32 and progress['counts']['dispatched']==32
        checks.append({'split':split,'report_package_complete':bool(passed),'integrity_gate':'Intention/journal and report agree; all planned slots dispatched/terminal. No quality threshold.','quality_threshold':None,'native_reexecutions':0})
    result={'schema_version':1,'passed':all(c['report_package_complete'] for c in checks),'checks':checks,'hosted_ci_executed':False,'model_calls':0,'external_calls':0}
    (out/'receipt.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
