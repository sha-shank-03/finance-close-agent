"""Prepared bounded paired evaluation. Native task execution requires a lease."""
import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

from .u2b_verify import verify
from .u2c_progress import atomic_write, counts as slot_counts, execute_slots
ROOT=Path(__file__).resolve().parent.parent


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):atomic_write(p,v)
def frozen():
    path=ROOT/'evaluation/u2b/manifest.json';manifest=json.loads(path.read_text(encoding='utf-8'))
    rows=manifest['records']
    if len(rows)!=32 or len({r['case_id'] for r in rows})!=32:raise ValueError('32 unique authored records required')
    for split in ['dev','capability']:
        group=[r for r in rows if r['split']==split]
        if len(group)!=16 or any(sum(r['stratum']==s for r in group)!=2 for s in manifest['strata']):raise ValueError('16 per split, eight strata twice')
    for r in rows:
        source=ROOT/r['input'];label=ROOT/r['label']
        if source.resolve()!=ROOT/'fixtures/u2b'/r['split']/r['case_id'] or label.resolve()!=ROOT/'evaluation/u2b/labels'/r['split']/(r['case_id']+'.json'):raise ValueError('Authored path scope')
        if {p.relative_to(ROOT).as_posix() for p in source.rglob('*') if p.is_file()}!=set(r['files']):raise ValueError('Input file set drift')
        if any(sha(ROOT/n)!=wanted for n,wanted in r['files'].items()) or sha(label)!=r['label_sha256']:raise ValueError('Authored freeze changed')
    return manifest,sha(path)


def wilson(wins,total):
    if not total:return None
    z=1.96;p=wins/total;d=1+z*z/total
    center=(p+z*z/(2*total))/d;radius=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/d
    return [max(0,center-radius),min(1,center+radius)]


def summary(rows):
    # Legacy completed rows are supported only for old component callers.
    rows=[r if 'state' in r else {**r,'state':'TERMINAL' if r.get('exit_code') is not None else 'INTERRUPTED_UNKNOWN','dispatch_confirmed':r.get('elapsed_seconds') is not None} for r in rows]
    rows=[r if r['state']=='TERMINAL' else {**r,'score':None} for r in rows]
    result={**slot_counts(rows),'attempted':sum(r.get('dispatch_confirmed',False) for r in rows),'execution_errors':sum(r['state']=='TERMINAL' and (r['exit_code']!=0 or r.get('error_class') is not None) for r in rows)}
    scored=[r['score'] for r in rows if r.get('score') is not None]
    for key in ['raw_exact_state_success','resolved_completion','correct_handoff']:
        n=sum(bool(r['state']=='TERMINAL' and r.get('dispatch_confirmed') and r.get('score') and r['score'][key] and r['exit_code']==0 and not r.get('error_class')) for r in rows);result[key]={'numerator':n,'denominator':len(rows),'value':n/len(rows) if rows else None,'wilson95_authored_descriptive':wilson(n,len(rows))}
    for metric in ['matches','holds','proposals']:
        counts={k:sum(s['metrics'][metric][k] for s in scored) for k in ['tp','predicted','gold']}
        # All gold denominators remain counted on failed/unscored attempts.
        for r in rows:
            if r.get('score') is None:counts['gold']+=r['gold_counts'][metric]
        counts['precision']=counts['tp']/counts['predicted'] if counts['predicted'] else None
        counts['unknown_prediction_slots']=len(rows)-len(scored)
        counts['recall']=counts['tp']/counts['gold'] if counts['gold'] else None;result[metric]=counts
    material_gold=sum(r['gold_counts']['material'] for r in rows)
    missed=sum(s['metrics']['material']['missed'] for s in scored)+sum(r['gold_counts']['material'] for r in rows if r.get('score') is None)
    result['material']={'missed':missed,'gold':material_gold,'unverified_gold':sum(r['gold_counts']['material'] for r in rows if r.get('score') is None),'value':missed/material_gold if material_gold else None}
    known=[s for s in scored if 'unsafe_committed' in s]
    unsafe=sum(s['unsafe_committed'] for s in known)
    result['unsafe_committed']={'observed_numerator':unsafe,'observed_denominator':len(known),'unknown_attempts':len(rows)-len(known),'value':unsafe/len(rows) if rows and len(known)==len(rows) else None}
    result['human_handoff_present']={'observed_numerator':sum(bool(s.get('human_handoff_present')) for s in scored),'observed_denominator':len(scored),'unknown_attempts':len(rows)-len(scored)}
    times=sorted(r['elapsed_seconds'] for r in rows if r['state']=='TERMINAL' and r.get('dispatch_confirmed') and 'elapsed_seconds' in r)
    result['latency_seconds']={'observed_attempts':len(times),'minimum':times[0] if times else None,'median':(times[(len(times)-1)//2]+times[len(times)//2])/2 if times else None,'p95_nearest_rank':times[math.ceil(.95*len(times))-1] if times else None,'maximum':times[-1] if times else None}
    result.update(model_calls=sum(s.get('model_calls',0) for s in scored) if len(scored)==len(rows) else None,actual_cost=None,cost_reason='No billed cost measurement; interrupted/unexecuted outcomes unknown. Fixed offline policies configure no paid requests.')
    return result


def evaluate(split,out,max_seconds=180):
    manifest,pin=frozen();out=Path(out).resolve()
    if out.exists() or out==ROOT or out.is_relative_to(ROOT/'fixtures') or out.is_relative_to(ROOT/'evaluation'):raise ValueError('Fresh artifact output required')
    out.mkdir(parents=True);started=time.monotonic();planned=[]
    code={p.relative_to(ROOT).as_posix():sha(p) for folder in ['finance_close','evaluation'] for p in sorted((ROOT/folder).glob('*.py'))}
    for record in [r for r in manifest['records'] if r['split']==split]:
        gold=json.loads((ROOT/record['label']).read_text(encoding='utf-8'))
        for policy in ['scripted','deterministic-v2']:
            run=out/record['case_id']/policy
            entry={'slot_id':record['case_id']+'::'+policy,'case_id':record['case_id'],'stratum':record['stratum'],'policy':policy,'run':str(run),'input':record['input'],'label':record['label'],'gold_counts':{'matches':len(gold['matches']),'holds':len(gold['exceptions']),'proposals':len(gold['proposals']),'material':sum(e['exposure_cents']>=10000 for e in gold['exceptions'])}}
            command=[sys.executable,'-m','finance_close.u2b','--input',str(ROOT/record['input']),'--out',str(run),'--policy',policy];entry['argv']=command
            planned.append(entry)
    rows,progress=execute_slots(planned,out,metadata={'split':split,'manifest_sha256':pin,'code_sha256':code},oracle=lambda row:verify(row['run'],ROOT/row['input'],ROOT/row['label']),max_seconds=max_seconds,cwd=ROOT,started_at=started)
    current=frozen()[1]
    paired={'scripted_wins':0,'ties':0,'deterministic_v2_wins':0,'unobserved_pairs':0,'pairs':[]}
    for record in [r for r in manifest['records'] if r['split']==split]:
        pair=[r for r in rows if r['case_id']==record['case_id']]
        success=[bool(r.get('score') and r['score']['passed'] and r['exit_code']==0 and not r.get('error_class')) if r['state']=='TERMINAL' and r.get('score') is not None else None for r in pair]
        kind='unobserved_pairs' if None in success else 'ties' if success[0]==success[1] else 'scripted_wins' if success[0] else 'deterministic_v2_wins'
        paired[kind]+=1;paired['pairs'].append({'case_id':record['case_id'],'result':kind,'success':success})
    report={'schema_version':2,'split':split,'unique_tasks':16,'planned_slots':len(rows),'attempts':progress['counts']['dispatched'],'progress':progress,'intended_manifest_sha256':sha(out/'intended.json'),'dispatch_journal_sha256':sha(out/'dispatch-events.jsonl') if (out/'dispatch-events.jsonl').exists() else None,'repetitions':1,'author_exposed':True,'manifest_sha256':pin,'manifest_unchanged':pin==current,'code_sha256':code,'code_unchanged':all(sha(ROOT/n)==v for n,v in code.items()),'batch_complete':progress['counts']['terminal']==len(rows) and not progress['stopped_early'],'max_seconds':max_seconds,'elapsed_seconds':time.monotonic()-started,'policies':{p:summary([r for r in rows if r['policy']==p]) for p in ['scripted','deterministic-v2']},'paired':paired,'quality_gate':None,'positive_uplift_required':False,'limitations':['All tasks author-exposed; shared issue construction families, not blind/external accuracy.','Two policies on16 unique tasks are32 planned slots, not32 independent tasks.','STARTED precedes launch; actual child confirmation is separate. Unfinished durable dispatch is unknown, never resumed.','Wilson intervals describe this authored set, not a population accuracy guarantee.','Cost/unsafe-committed outcomes require complete independent reports; no live-model measurement.'],'rows':rows}
    write(out/'report.json',report)
    # Quality results are reported, not converted into an unapproved threshold.
    return 0 if report['batch_complete'] and report['manifest_unchanged'] and report['code_unchanged'] else 1


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--split',choices=['dev','capability'],required=True);p.add_argument('--out',required=True);p.add_argument('--max-seconds',type=int,choices=[180],default=180)
    args=p.parse_args(argv)
    try:return evaluate(args.split,args.out,args.max_seconds)
    except Exception:print(json.dumps({'batch_complete':False,'error_class':'evaluation_failed'}));return 1


if __name__=='__main__':raise SystemExit(main())
