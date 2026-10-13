"""Leased U2-B native source-only entry point; labels never enter this process."""
import argparse
import hashlib
import json
from pathlib import Path

from .agent import investigate
from .deterministic_v2 import DeterministicV2, U2bTools
from .ingest import parse_bundle
from .providers import ScriptedProvider
from .render import write_packet
from .store import Store


def source_binding():
    root=Path(__file__).resolve().parent
    raw=json.dumps([[p.name,hashlib.sha256(p.read_bytes()).hexdigest()] for p in sorted(root.glob('*.py'))],separators=(',',':')).encode()
    return hashlib.sha256(raw).hexdigest()


def run(source,out,policy):
    source,out=Path(source).resolve(),Path(out).resolve()
    if out.exists() or out.is_relative_to(source) or source.is_relative_to(out):raise ValueError('Fresh separate output required')
    out.mkdir(parents=True)
    store=Store(out/'state.sqlite')
    try:
        store.initialize(parse_bundle(source,invoice_format='aliases-v1'))
        store.set_meta('u2b_code_hash',source_binding())
        store.set_meta('invoice_format','aliases-v1')
        store.set_meta('u2b_policy',policy)
        provider=DeterministicV2() if policy=='deterministic-v2' else ScriptedProvider()
        investigate(store,provider,tools_factory=U2bTools)
        write_packet(store,out)
    finally:store.close()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True);p.add_argument('--out',required=True)
    p.add_argument('--policy',choices=['scripted','deterministic-v2'],required=True)
    args=p.parse_args(argv)
    try:run(args.input,args.out,args.policy)
    except Exception:
        # Preserve database state; never claim completion on a rejected action.
        print(json.dumps({'completed':False,'error_class':'workflow_failed'}));return 4
    print(json.dumps({'completed':True,'evidence':'authored offline workflow; unposted','model_calls':0}));return 0


if __name__=='__main__':raise SystemExit(main())
