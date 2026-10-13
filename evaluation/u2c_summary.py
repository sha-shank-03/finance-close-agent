"""Immutable, allowlisted public projection of completed offline reports."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

POLICIES=['scripted','deterministic-v2']
STRATA=['exact','amounts','duplicates','missing_invoice','ap_missing','partial','fees','timing_unsupported']
EVIDENCE='historical author-exposed offline first reports; no rerun'
AUTHORSHIP='Worker-authored fictional MIT source/data; both splits exposed and share construction families'
LIMITS=['Small correlated authored tasks; no unseen/population or live-model accuracy claim.','Completed investigation is separate from resolved completion and correct handoff.','Unposted proposals do not change booked ledger or certify financial close.','Main unseen, genuine QBO sandbox, live inference, full regression and hosted CI remain pending.']
BUDGETS={'tools_per_case':10,'decisions_per_case':12,'decisions_per_run':250,'cases_per_run':50,'run_seconds':180,'split_seconds':180,'child_seconds':30}

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def require(condition):
    if not condition:raise ValueError('Invalid public summary or source report')
def integer(value):return type(value) is int and value>=0
def number(value):return type(value) in {int,float} and math.isfinite(value) and value>=0
def sha(value):return type(value) is str and re.fullmatch('[a-f0-9]{64}',value) is not None

def project(report,split,report_sha):
    require(report['split']==split and report['unique_tasks']==16 and report['repetitions']==1 and report['author_exposed'] is True)
    require(report['manifest_unchanged'] is True and report['code_unchanged'] is True and report['batch_complete'] is True)
    require(sha(report_sha) and sha(report['manifest_sha256']))
    code=report['code_sha256'];require(bool(code) and all(re.fullmatch('(finance_close|evaluation)/[a-z0-9_]+[.]py',n) and sha(v) for n,v in code.items()))
    rows=report['rows'];prefix='D' if split=='dev' else 'C'
    wanted={(prefix+str(s)+str(v),p) for s in range(1,9) for v in [1,2] for p in POLICIES}
    require(len(rows)==32 and {(r['case_id'],r['policy']) for r in rows}==wanted)
    safe=[]
    for r in rows:
        require(r['stratum']==STRATA[int(r['case_id'][1])-1] and type(r['exit_code']) is int and number(r['elapsed_seconds']))
        if report['schema_version']==2:require(r['state']=='TERMINAL' and r['dispatch_confirmed'] is True and not r.get('error_class'))
        else:require(report['schema_version']==1 and report['attempts']==32 and not r.get('error_class'))
        score=r['score'];require(type(score) is dict and score['actual_cost'] is None and score['model_calls']==0)
        require(all(type(score[k]) is bool for k in ['passed','raw_exact_state_success','resolved_completion','correct_handoff','unsafe_committed','human_handoff_present']))
        require(score['passed']==score['raw_exact_state_success'] and not (score['resolved_completion'] and score['correct_handoff']))
        require((score['resolved_completion'] or score['correct_handoff'])==score['passed'])
        metric={}
        for kind in ['matches','holds','proposals']:
            m=score['metrics'][kind];require(all(integer(m[k]) for k in ['tp','predicted','gold']) and m['tp']<=min(m['predicted'],m['gold']))
            require(m['gold']==r['gold_counts'][kind])
            metric[kind]={k:m[k] for k in ['tp','predicted','gold']}
        material=score['metrics']['material'];require(integer(material['gold']) and integer(material['missed']) and material['missed']<=material['gold'] and material['gold']==r['gold_counts']['material'])
        complete=any(c['name']=='all cases complete exactly once' and c['passed'] is True for c in score['checks']) and any(c['name']=='run genuinely packet ready' and c['passed'] is True for c in score['checks'])
        require(complete)
        extra=[]
        for h in score['metrics']['holds']['unexpected']:
            require(len(h)==4 and h[2] in {'INCOMPLETE_HISTORY','MISSING_INVOICE','CONFLICTING_EVIDENCE','AMBIGUOUS_MATCH','OVERPAYMENT','UNMATCHED_CASH','UNMATCHED_LEDGER','AMOUNT_CONFLICT','TIMING_DIFFERENCE','UNSUPPORTED_CURRENCY','UNSUPPORTED_TRANSACTION'} and integer(h[3]))
            extra.append({'reason':h[2],'exposure_cents':h[3]})
        failures=[c['name'] for c in score['failures']]
        require(all(name=='exact independently labeled holds' for name in failures))
        safe.append({'case_id':r['case_id'],'policy':r['policy'],'stratum':r['stratum'],'native_exit_code':r['exit_code'],'investigation_completed':complete,'raw_exact_state_success':score['passed'] and r['exit_code']==0,'resolved_completion':score['resolved_completion'] and r['exit_code']==0,'correct_handoff':score['correct_handoff'] and r['exit_code']==0,'human_handoff_present':score['human_handoff_present'],'unsafe_committed':score['unsafe_committed'],'elapsed_seconds':r['elapsed_seconds'],'metrics':metric,'material':{'gold':material['gold'],'missed':material['missed']},'extra_holds':extra,'exact_hold_assertion_failed':bool(failures)})
    return {'split':split,'first_report_sha256':report_sha,'first_code_sha256':code,'first_code_fingerprint':digest(code),'dataset_manifest_sha256':report['manifest_sha256'],'unique_tasks':16,'planned_slots':32,'dispatched':32,'terminal':32,'rows':safe}

def aggregate(rows):
    result={'planned':len(rows),'dispatched':len(rows),'terminal':len(rows),'investigation_completed':sum(r['investigation_completed'] for r in rows),'raw_exact_state_success':sum(r['raw_exact_state_success'] for r in rows),'resolved_completion':sum(r['resolved_completion'] for r in rows),'correct_handoff':sum(r['correct_handoff'] for r in rows),'human_handoff_present':sum(r['human_handoff_present'] for r in rows),'unsafe_committed':{'observed':sum(r['unsafe_committed'] for r in rows),'coverage':len(rows),'unknown':0},'actual_measured_cost':None}
    for kind in ['matches','holds','proposals']:
        m={k:sum(r['metrics'][kind][k] for r in rows) for k in ['tp','predicted','gold']}
        result[kind]={**m,'precision':m['tp']/m['predicted'] if m['predicted'] else None,'recall':m['tp']/m['gold'] if m['gold'] else None}
    result['material']={'gold':sum(r['material']['gold'] for r in rows),'missed':sum(r['material']['missed'] for r in rows),'unit':'labeled holds with exposure >=10000 cents, not distinct cash losses'}
    times=sorted(r['elapsed_seconds'] for r in rows)
    result['latency_seconds']={'coverage':len(times),'denominator':len(rows),'median':(times[(len(times)-1)//2]+times[len(times)//2])/2,'p95_nearest_rank':times[math.ceil(.95*len(times))-1],'min':times[0],'max':times[-1],'scope':'actor dispatch through independent verification; completed attempts only'}
    return result

def derive(splits):
    quality={s['split']:{p:aggregate([r for r in s['rows'] if r['policy']==p]) for p in POLICIES} for s in splits}
    paired={'pairs':32,'scripted_wins':0,'deterministic_v2_wins':0,'ties':0}
    for s in splits:
        for case in sorted({r['case_id'] for r in s['rows']}):
            outcomes=[next(r['raw_exact_state_success'] for r in s['rows'] if r['case_id']==case and r['policy']==p) for p in POLICIES]
            paired['ties' if outcomes[0]==outcomes[1] else 'scripted_wins' if outcomes[0] else 'deterministic_v2_wins']+=1
    return quality,paired

def build(dev,capability,dev_sha,capability_sha):
    splits=[project(dev,'dev',dev_sha),project(capability,'capability',capability_sha)]
    require(splits[0]['first_code_sha256']==splits[1]['first_code_sha256'] and splits[0]['dataset_manifest_sha256']==splits[1]['dataset_manifest_sha256'])
    quality,paired=derive(splits)
    result={'schema_version':1,'summary_version':'u2b-public-first-v1','evidence_type':EVIDENCE,'authorship':AUTHORSHIP,'unique_tasks':32,'planned_slots':64,'dispatched':64,'terminal':64,'repetitions':1,'separate_demo_adds_unique_tasks':False,'equal_budgets':BUDGETS,'model_calls':0,'external_calls':0,'actual_measured_cost':None,'quality_gate':None,'positive_uplift_required':False,'splits':splits,'quality':quality,'paired':paired,'limits':LIMITS}
    validate(result);return result

def validate(value):
    # Reject unapproved extra fields recursively by rebuilding canonical projection.
    require(set(value)=={'schema_version','summary_version','evidence_type','authorship','unique_tasks','planned_slots','dispatched','terminal','repetitions','separate_demo_adds_unique_tasks','equal_budgets','model_calls','external_calls','actual_measured_cost','quality_gate','positive_uplift_required','splits','quality','paired','limits'})
    require(value['schema_version']==1 and value['summary_version']=='u2b-public-first-v1' and value['unique_tasks']==32 and value['planned_slots']==value['dispatched']==value['terminal']==64 and value['repetitions']==1)
    require(value['actual_measured_cost'] is None and value['model_calls']==value['external_calls']==0 and value['quality_gate'] is None and value['positive_uplift_required'] is False)
    require(value['evidence_type']==EVIDENCE and value['authorship']==AUTHORSHIP and value['limits']==LIMITS and value['equal_budgets']==BUDGETS and value['separate_demo_adds_unique_tasks'] is False)
    require([s['split'] for s in value['splits']]==['dev','capability'])
    for s in value['splits']:
        require(set(s)=={'split','first_report_sha256','first_code_sha256','first_code_fingerprint','dataset_manifest_sha256','unique_tasks','planned_slots','dispatched','terminal','rows'})
        require(sha(s['first_report_sha256']) and sha(s['dataset_manifest_sha256']) and s['first_code_fingerprint']==digest(s['first_code_sha256']))
        require(bool(s['first_code_sha256']) and all(re.fullmatch('(finance_close|evaluation)/[a-z0-9_]+[.]py',n) and sha(v) for n,v in s['first_code_sha256'].items()))
        require(s['unique_tasks']==16 and s['planned_slots']==s['dispatched']==s['terminal']==32)
        require(len(s['rows'])==32 and len({(r['case_id'],r['policy']) for r in s['rows']})==32)
        for r in s['rows']:
            require(set(r)=={'case_id','policy','stratum','native_exit_code','investigation_completed','raw_exact_state_success','resolved_completion','correct_handoff','human_handoff_present','unsafe_committed','elapsed_seconds','metrics','material','extra_holds','exact_hold_assertion_failed'})
            require(re.fullmatch(('D' if s['split']=='dev' else 'C')+'[1-8][12]',r['case_id']) is not None and r['policy'] in POLICIES and r['stratum']==STRATA[int(r['case_id'][1])-1] and type(r['native_exit_code']) is int and number(r['elapsed_seconds']))
            require(all(type(r[k]) is bool for k in ['investigation_completed','raw_exact_state_success','resolved_completion','correct_handoff','human_handoff_present','unsafe_committed','exact_hold_assertion_failed']))
            require(r['investigation_completed'] is True and r['raw_exact_state_success']==(r['resolved_completion'] or r['correct_handoff']) and not(r['resolved_completion'] and r['correct_handoff']))
            require(set(r['metrics'])=={'matches','holds','proposals'})
            for m in r['metrics'].values():require(set(m)=={'tp','predicted','gold'} and all(integer(v) for v in m.values()) and m['tp']<=min(m['predicted'],m['gold']))
            require(set(r['material'])=={'gold','missed'} and all(integer(v) for v in r['material'].values()) and r['material']['missed']<=r['material']['gold'])
            for h in r['extra_holds']:require(set(h)=={'reason','exposure_cents'} and h['reason']=='INCOMPLETE_HISTORY' and integer(h['exposure_cents']))
            require(len(r['extra_holds'])==r['metrics']['holds']['predicted']-r['metrics']['holds']['tp'])
    require(value['splits'][0]['first_code_sha256']==value['splits'][1]['first_code_sha256'] and value['splits'][0]['dataset_manifest_sha256']==value['splits'][1]['dataset_manifest_sha256'])
    quality,paired=derive(value['splits']);require(value['quality']==quality and value['paired']==paired)
    text=canonical(value).decode();require(not any(word in text for word in ['C:\\','C:/','/'+'Users'+'/','coordination/','sqlite','argv','owned_pid']))
    return True

def export(dev_path,capability_path,out):
    dev_path,capability_path,out=Path(dev_path),Path(capability_path),Path(out)
    require(not out.exists());dev_bytes=dev_path.read_bytes();cap_bytes=capability_path.read_bytes()
    value=build(json.loads(dev_bytes),json.loads(cap_bytes),hashlib.sha256(dev_bytes).hexdigest(),hashlib.sha256(cap_bytes).hexdigest())
    out.mkdir(parents=True);raw=(json.dumps(value,indent=2)+'\n').encode()
    with (out/'summary.json').open('xb') as stream:stream.write(raw)
    pins={'schema_version':1,'summary_sha256':hashlib.sha256(raw).hexdigest(),'first_report_sha256':{s['split']:s['first_report_sha256'] for s in value['splits']},'first_code_fingerprint':value['splits'][0]['first_code_fingerprint']}
    with (out/'manifest.json').open('xb') as stream:stream.write((json.dumps(pins,indent=2)+'\n').encode())
    return value

def validate_bundle(out):
    out=Path(out);raw=(out/'summary.json').read_bytes();value=json.loads(raw);pins=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    validate(value);require(set(pins)=={'schema_version','summary_sha256','first_report_sha256','first_code_fingerprint'} and pins['schema_version']==1 and pins['summary_sha256']==hashlib.sha256(raw).hexdigest() and pins['first_report_sha256']=={s['split']:s['first_report_sha256'] for s in value['splits']} and pins['first_code_fingerprint']==value['splits'][0]['first_code_fingerprint'])
    return True

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    e=sub.add_parser('export');e.add_argument('--dev-report',required=True);e.add_argument('--capability-report',required=True);e.add_argument('--out',required=True)
    v=sub.add_parser('validate');v.add_argument('--bundle',required=True)
    args=p.parse_args(argv)
    try:
        if args.action=='export':export(args.dev_report,args.capability_report,args.out)
        else:validate_bundle(args.bundle)
    except Exception:print(json.dumps({'passed':False,'error_class':'summary_rejected'}));return 1
    print(json.dumps({'passed':True,'native_reexecutions':0,'actual_measured_cost':None}));return 0

if __name__=='__main__':raise SystemExit(main())
