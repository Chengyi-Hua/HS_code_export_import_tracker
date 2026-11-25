import argparse,json,uuid
from datetime import datetime,timezone
import pandas as pd
from engine import ROOT,plan,collect,discover
p=argparse.ArgumentParser(description='Retrieve UN Comtrade or synthetic data and save a dashboard run')
p.add_argument('--frequency',choices=['A','M','auto'],default='A');p.add_argument('--hs',nargs='+',default=['28539030','28539050']);p.add_argument('--reporters',nargs='+',default=['156']);p.add_argument('--start',default=None);p.add_argument('--end',default='latest');p.add_argument('--flows',nargs='+',default=['M','X'],choices=['M','X']);p.add_argument('--partners',nargs='*',default=[]);p.add_argument('--budget',type=int,default=100);p.add_argument('--demo',action='store_true');p.add_argument('--refresh',action='store_true');p.add_argument('--plan',action='store_true');p.add_argument('--discover',action='store_true');a=p.parse_args();q=dict(frequency=a.frequency,codes=' '.join(a.hs),reporters=a.reporters,start=a.start or ('2024' if a.frequency=='A' else '2025-01'),end=(str(datetime.now(timezone.utc).year-1) if a.frequency=='A' else str(pd.Period(datetime.now(timezone.utc).strftime('%Y-%m'))-1)) if a.end=='latest' else a.end,flows=a.flows,partners=a.partners,budget=a.budget,demo=a.demo,refresh=a.refresh);t,j=plan(q);print(f'{len(j)} jobs, up to {sum(len(x[1]["aliases"]) for x in j)} attempts');print(json.dumps(t,indent=2))
if a.discover:
 print(json.dumps(discover(q,max_attempts=q['budget']),indent=2));raise SystemExit(0)
if not a.plan:
 r=collect(q,lambda x:print(x['message'],flush=True));r['id']=uuid.uuid4().hex;d=ROOT/'data'/'runs';d.mkdir(parents=True,exist_ok=True);(d/(r['id']+'.json')).write_text(json.dumps(r),encoding='utf8');print(f"Saved {len(r['rows'])} rows. Open dashboard and select {r['id']}.");raise SystemExit(0 if r['rows'] and all(x['status'] in ['downloaded','cached','synthetic'] and not x['conflicts'] and not x['excluded'] for x in r['audit']) else 2)
