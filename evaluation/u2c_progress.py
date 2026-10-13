"""Durable offline dispatch accounting; no resume or implicit redispatch."""
import copy
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

STATES={'PLANNED','STARTED','DISPATCHED','CHILD_RETURNED','TERMINAL','DEADLINE_UNEXECUTED','INTERRUPTED_UNKNOWN'}
TRANSITIONS={'PLANNED':{'STARTED','DEADLINE_UNEXECUTED'},'STARTED':{'DISPATCHED','TERMINAL','DEADLINE_UNEXECUTED','INTERRUPTED_UNKNOWN'},'DISPATCHED':{'CHILD_RETURNED','INTERRUPTED_UNKNOWN'},'CHILD_RETURNED':{'TERMINAL','INTERRUPTED_UNKNOWN'}}

def encoded(value):
    return (json.dumps(value,indent=2,default=lambda v:hashlib.sha256(v).hexdigest() if type(v) is bytes else (_ for _ in ()).throw(TypeError('Unsupported JSON value')))+'\n').encode()

def atomic_write(path,value):
    path=Path(path);temporary=path.with_name(path.name+'.tmp')
    with temporary.open('wb') as stream:stream.write(encoded(value));stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)

def counts(rows):
    return {'planned':len(rows),'dispatch_started':sum(r.get('dispatch_started',False) for r in rows),'dispatched':sum(r.get('dispatch_confirmed',False) for r in rows),'terminal':sum(r['state']=='TERMINAL' for r in rows),'deadline_unexecuted':sum(r['state']=='DEADLINE_UNEXECUTED' for r in rows),'interrupted_unknown':sum(r['state']=='INTERRUPTED_UNKNOWN' for r in rows),'dispatch_unknown':sum(r['state']=='INTERRUPTED_UNKNOWN' and not r.get('dispatch_confirmed',False) for r in rows),'pending_unexecuted':sum(r['state']=='PLANNED' for r in rows)}

def native_dispatch(command,*,cwd,timeout,on_launched):
    """One retained child. Confirm actual creation; kill/join on timeout/error."""
    process=subprocess.Popen(command,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        on_launched(process.pid)
        try:
            stdout,stderr=process.communicate(timeout=timeout);error=None
        except subprocess.TimeoutExpired:
            process.kill();stdout,stderr=process.communicate(timeout=2);error='task_deadline'
        result=subprocess.CompletedProcess(command,process.returncode,stdout,stderr)
        result.error_class=error
        return result
    except BaseException:
        # Cleanup failure leaves the durable PID for the outer lease observer.
        try:
            if process.poll() is None:process.kill()
            process.communicate(timeout=2)
        except Exception:pass
        raise
    finally:
        if process.poll() is not None:
            process.stdout.close();process.stderr.close()

def execute_slots(planned,out,*,metadata,dispatch=native_dispatch,oracle,clock=time.monotonic,max_seconds=180,cwd=None,started_at=None):
    """Inject dispatch/oracle/clock for pure tests; persist before every launch."""
    started=clock() if started_at is None else started_at
    out=Path(out);rows=copy.deepcopy(planned)
    for row in rows:row.update(state='PLANNED',dispatch_started=False,dispatch_confirmed=False,exit_code=None,score=None,actual_cost=None)
    if len({r['slot_id'] for r in rows})!=len(rows):raise ValueError('Unique intended slots required')
    intention={'schema_version':2,'metadata':metadata,'slots':rows,'slots_sha256':hashlib.sha256(encoded(rows)).hexdigest()}
    with (out/'intended.json').open('xb') as stream:stream.write(encoded(intention));stream.flush();os.fsync(stream.fileno())
    atomic_write(out/'case-results.json',rows)
    sequence=0;stopped=False
    def persist(row,state,**changes):
        nonlocal sequence
        if state not in TRANSITIONS.get(row['state'],set()):raise ValueError('Illegal dispatch transition')
        proposed={**row,**changes,'state':state};event={'sequence':sequence+1,'slot_id':row['slot_id'],'entry':proposed}
        with (out/'dispatch-events.jsonl').open('ab') as stream:
            stream.write(json.dumps(event,default=lambda v:hashlib.sha256(v).hexdigest() if type(v) is bytes else (_ for _ in ()).throw(TypeError())).encode()+b'\n');stream.flush();os.fsync(stream.fileno())
        sequence+=1;row.clear();row.update(proposed);atomic_write(out/'case-results.json',rows)
    for row in rows:
        remaining=max_seconds-(clock()-started)
        if remaining<=.1:
            persist(row,'DEADLINE_UNEXECUTED',error_class='batch_deadline');continue
        before=clock()
        launch_observed=None
        def launched(pid):
            nonlocal launch_observed
            launch_observed=pid
            persist(row,'DISPATCHED',dispatch_confirmed=True,owned_pid=pid)
        try:
            persist(row,'STARTED',dispatch_started=True)
            remaining=max_seconds-(clock()-started)
            if remaining<=.1:
                persist(row,'DEADLINE_UNEXECUTED',error_class='batch_deadline_before_launch');continue
            result=dispatch(row['argv'],cwd=cwd,timeout=min(30,remaining),on_launched=launched)
            if not row['dispatch_confirmed']:raise RuntimeError('Dispatcher returned without launch confirmation')
            persist(row,'CHILD_RETURNED',exit_code=result.returncode,error_class=getattr(result,'error_class',None))
            run=Path(row['run']);run.mkdir(parents=True,exist_ok=True)
            (run/'stdout.log').write_bytes(result.stdout);(run/'stderr.log').write_bytes(result.stderr)
            score=None;verification_error=None
            try:score=oracle(row);atomic_write(run/'independent.json',score)
            except Exception:score=None;verification_error='missing_or_invalid_state'
            persist(row,'TERMINAL',score=score,verification_error_class=verification_error,elapsed_seconds=clock()-before)
        except OSError:
            if row['state']=='STARTED' and launch_observed is None:
                persist(row,'TERMINAL',error_class='launch_error')
            else:
                if row['state'] in TRANSITIONS and 'INTERRUPTED_UNKNOWN' in TRANSITIONS[row['state']]:persist(row,'INTERRUPTED_UNKNOWN',error_class='lost_result_or_storage_error',dispatch_confirmed=launch_observed is not None,**({'owned_pid':launch_observed} if launch_observed is not None else {}))
                stopped=True;break
        except BaseException:
            if row['state'] in TRANSITIONS and 'INTERRUPTED_UNKNOWN' in TRANSITIONS[row['state']]:persist(row,'INTERRUPTED_UNKNOWN',error_class='interrupted_result_unknown',dispatch_confirmed=launch_observed is not None,**({'owned_pid':launch_observed} if launch_observed is not None else {}))
            stopped=True;break
    return rows,{'stopped_early':stopped,'counts':counts(rows),'elapsed_observed_seconds':clock()-started}

def read_progress(out):
    """Read the authoritative intention/journal; incomplete launch stays unknown."""
    out=Path(out);intention=json.loads((out/'intended.json').read_text(encoding='utf-8'))
    rows=intention['slots']
    if hashlib.sha256(encoded(rows)).hexdigest()!=intention['slots_sha256']:raise ValueError('Intended slots changed')
    by_id={r['slot_id']:r for r in rows};tail=False;events=out/'dispatch-events.jsonl'
    lines=events.read_bytes().splitlines(keepends=True) if events.exists() else []
    for n,line in enumerate(lines,1):
        if not line.endswith(b'\n') and n==len(lines):tail=True;break
        event=json.loads(line);row=by_id[event['slot_id']];entry=event['entry']
        if event['sequence']!=n or entry['state'] not in TRANSITIONS.get(row['state'],set()):raise ValueError('Invalid progress journal')
        for key in ['slot_id','case_id','policy','stratum','gold_counts','argv','run']:
            if entry[key]!=row[key]:raise ValueError('Intended slot drift')
        row.clear();row.update(entry)
    for row in rows:
        if row['state'] in {'STARTED','DISPATCHED','CHILD_RETURNED'}:
            row['last_durable_state']=row['state'];row['state']='INTERRUPTED_UNKNOWN';row['score']=None
            row.pop('elapsed_seconds',None)
    return {'metadata':intention['metadata'],'rows':rows,'counts':counts(rows),'partial_journal_tail':tail,'redispatch_permitted':False}

def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description='Read durable dispatch counts without resuming');p.add_argument('--run',required=True);args=p.parse_args(argv)
    try:
        value=read_progress(args.run)
        print(json.dumps({k:value[k] for k in ['counts','partial_journal_tail','redispatch_permitted']}));return 0 if not value['partial_journal_tail'] else 1
    except Exception:print(json.dumps({'passed':False,'error_class':'progress_rejected'}));return 1

if __name__=='__main__':raise SystemExit(main())
