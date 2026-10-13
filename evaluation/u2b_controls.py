"""Prepared five negative controls on COPIES of a leased native proposal run."""
import argparse
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
from .u2b_verify import verify


def mutate(db,packet,kind):
    if kind=='one-cent':db.execute('UPDATE proposal_lines SET amount_cents=amount_cents+1 WHERE number=0')
    elif kind=='deleted-hold':
        # Caller supplies a native handoff run with a real expected hold.
        db.execute('DELETE FROM exceptions WHERE id=(SELECT id FROM exceptions LIMIT 1)')
    elif kind=='forged-match':
        db.execute('PRAGMA foreign_keys=OFF');db.execute("INSERT OR REPLACE INTO matches VALUES ('FORGED-BANK','FORGED-LINE','[]')")
    elif kind=='provenance':
        row=db.execute('SELECT id,content FROM proposals LIMIT 1').fetchone();value=json.loads(row[1]);value['evidence_ids']=[];db.execute('UPDATE proposals SET content=? WHERE id=?',(json.dumps(value),row[0]))
    elif kind=='false-completion':
        db.execute("UPDATE cases SET state='OPEN'");packet['run_state']='PACKET_READY'
    else:raise ValueError('Unknown negative control')
    db.commit()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['proposal-run','handoff-run','out']:p.add_argument('--'+name,required=True)
    args=p.parse_args(argv);root=Path(__file__).resolve().parent.parent;out=Path(args.out)
    if out.exists():raise ValueError('Fresh mutation output required')
    out.mkdir(parents=True);checks=[];baseline=[];pins={}
    for name,key in [(args.proposal_run,'D51'),(args.handoff_run,'D62')]:
        base=Path(name)
        pins[name]={p.relative_to(base).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in base.rglob('*') if p.is_file()}
        try:
            result=verify(base,root/'fixtures/u2b/dev'/key,root/'evaluation/u2b/labels/dev'/(key+'.json'))
            eligible=result['passed'] and result['metrics']['proposals' if key=='D51' else 'holds']['predicted']>0
        except Exception:eligible=False
        baseline.append({'case_id':key,'independent_baseline_passed':eligible})
    if not all(c['independent_baseline_passed'] for c in baseline):
        (out/'receipt.json').write_bytes((json.dumps({'passed':False,'baseline':baseline,'controls':[],'error_class':'positive_baseline_failed'},indent=2)+'\n').encode());return 1
    for kind in ['one-cent','deleted-hold','forged-match','provenance','false-completion']:
        base=Path(args.handoff_run if kind=='deleted-hold' else args.proposal_run);key='D62' if kind=='deleted-hold' else 'D51'
        run=out/kind;shutil.copytree(base,run)
        packet=json.loads((run/'packet.json').read_text(encoding='utf-8'));db=sqlite3.connect(run/'state.sqlite')
        try:mutate(db,packet,kind)
        finally:db.close()
        (run/'packet.json').write_bytes((json.dumps(packet,indent=2)+'\n').encode())
        try:
            result=verify(run,root/'fixtures/u2b/dev'/key,root/'evaluation/u2b/labels/dev'/(key+'.json'));rejected=not result['passed']
            detail={'assertions':result['assertions'],'failed_assertions':[c['name'] for c in result['failures']]}
        except Exception:rejected=True;detail={'error_class':'corrupt_state_rejected'}
        checks.append({'control':kind,'rejected':rejected,**detail})
    unchanged=all(pins[name]=={p.relative_to(Path(name)).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(name).rglob('*') if p.is_file()} for name in pins)
    passed=all(c['rejected'] for c in checks) and unchanged
    (out/'receipt.json').write_bytes((json.dumps({'controls':checks,'baseline':baseline,'passed':passed,'original_runs_modified':not unchanged},indent=2)+'\n').encode())
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
