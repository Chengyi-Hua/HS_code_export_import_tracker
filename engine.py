"""Frequency-aware UN Comtrade retrieval. No synthetic fallback for live requests."""
import os,json,time,hashlib,re,math
from pathlib import Path
from datetime import datetime,timezone
import pandas as pd
import requests,pycountry
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT/".env")
REG=json.loads((ROOT/'hs_registry.json').read_text())
COUNTRIES={str(int(c.numeric)): {'name':c.name,'iso':c.alpha_3} for c in pycountry.countries if hasattr(c,'numeric')}
for k,n in {'156':'China','410':'South Korea','360':'Indonesia','504':'Morocco','392':'Japan','276':'Germany','842':'United States','704':'Vietnam','158':'Taiwan'}.items():
 if k in COUNTRIES: COUNTRIES[k]['name']=n
COUNTRIES['490']={'name':'Other Asia, nes','iso':'TWN'}
COUNTRIES['0']={'name':'World','iso':None}
BASE='https://comtradeapi.un.org'
CACHE=ROOT/'data'/'cache_v34'; CACHE.mkdir(parents=True,exist_ok=True)
COLS=['period','reporter','hs','flow','partner','partner_name','iso','kg','usd','priced_kg','priced_usd','scope','source_hs','tier','estimated','classification','frequency','source_rows']
def ident(x):
 try:return str(int(x))
 except:return str(x or '')
def num(x):
 try:
  v=float(x); return v if math.isfinite(v) and v>=0 else None
 except:return None
def targets(codes,reporters):
 result={}
 for token in codes.replace(',',' ').split():
  if ':' in token: r,h=token.split(':',1); rr=[r]
  else:
   h=token; found={x['reporter'] for x in REG if h in x['aliases'] and len(h)>6}; rr=sorted(found) if len(found)==1 else reporters if len(h)==6 else []
  if not rr or not re.fullmatch(r'\d{6}|\d{8,12}',h): raise ValueError('Use six digits or reporter: national code (8–12 digits).')
  for r in rr:
   if r not in reporters: raise ValueError(f'Reporter {r} not selected; select it explicitly.')
   match=next((x for x in REG if x['reporter']==r and h in x['aliases']),None)
   t=match or dict(reporter=r,code=h,aliases=[h],tier='custom_unverified',label='User-defined; verify classification',dataset='final' if len(h)==6 else 'tariffline')
   result[(r,t['code'])]=t
 if not result: raise ValueError('Select at least one code.')
 return list(result.values())
def period_frequency(period):
 return 'A' if len(str(period))==4 else 'M'

def period_list(q, frequency):
 start,end=q['start'],q['end']; now=datetime.now(timezone.utc)
 if frequency=='A':
  start,end=str(start)[:4],str(end)[:4]
  if not re.fullmatch(r'\d{4}',start) or not re.fullmatch(r'\d{4}',end):raise ValueError('Annual dates must identify years.')
  periods=list(pd.period_range(start,end,freq='Y'))
  if not periods or len(periods)>30 or periods[-1].year>=now.year:raise ValueError('Select 1–30 completed years.')
 else:
  if not all(re.fullmatch(r'\d{4}-\d{2}',v) for v in [start,end]):raise ValueError('Monthly dates must be YYYY-MM.')
  periods=list(pd.period_range(start,end,freq='M'))
  if not periods or len(periods)>120 or periods[-1]>=pd.Period(now.strftime('%Y-%m'),freq='M'):raise ValueError('Select 1–120 completed months.')
 return [str(p) for p in periods]

def plan(q):
 ts=targets(q['codes'],q['reporters']); frequency=q.get('frequency','M')
 if frequency not in ('A','M','auto'):raise ValueError('Invalid reporting frequency.')
 if not q['flows'] or set(q['flows'])-{'M','X'}:raise ValueError('Select imports and/or exports.')
 if not 1<=int(q['budget'])<=1000:raise ValueError('Budget must be 1–1000.')
 if any(r not in COUNTRIES or r=='0' for r in q['reporters']):raise ValueError('Invalid reporter.')
 if any(r not in COUNTRIES for r in q.get('partners',[])):raise ValueError('Invalid partner.')
 jobs=[]
 # In auto mode request complete annual years first, then monthly series; never combine them.
 if frequency in ('A','auto'):
  aq=dict(q)
  if frequency=='auto':aq['end']=str(min(int(q['end'][:4]),datetime.now(timezone.utc).year-1))
  if int(aq['start'][:4])<=int(aq['end'][:4]):
   jobs += [(p,t,f) for p in reversed(period_list(aq,'A')) for t in ts for f in q['flows']]
 if frequency in ('M','auto'):
  jobs += [(p,t,f) for p in reversed(period_list(q,'M')) for t in ts for f in q['flows']]
 if not jobs or len(jobs)>5000:raise ValueError('No valid periods or too many jobs; narrow selection.')
 return ts,jobs

def _payload(session,url,params,key,refresh):
 # Content-address raw snapshots; index by request signature. A refresh never overwrites older evidence.
 sig=hashlib.sha256(json.dumps([url,params,bool(key)],sort_keys=True).encode()).hexdigest(); idx=CACHE/(sig+'.index')
 if idx.exists() and not refresh and time.time()-idx.stat().st_mtime<86400:
  token=idx.read_text().strip(); path=CACHE/(token+'.json')
  if path.exists():return json.loads(path.read_text(encoding='utf-8')),'cached',token
 response=session.get(url,params=params,headers={'Ocp-Apim-Subscription-Key':key} if key else {},timeout=(8,75));response.raise_for_status();payload=response.json()
 if not isinstance(payload,dict) or not isinstance(payload.get('data'),list) or payload.get('error'):raise ValueError('API returned an invalid/error payload')
 snap={'url':url,'params':params,'http':response.status_code,'retrieved':datetime.now(timezone.utc).isoformat(),'payload':payload}
 token=hashlib.sha256(json.dumps(snap,sort_keys=True).encode()).hexdigest();path=CACHE/(token+'.json');tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(snap),encoding='utf-8');tmp.replace(path);idx.write_text(token);time.sleep(1.1)
 return snap,'downloaded',token

def request_data(session,t,period,flow,code,partners,key,refresh):
 endpoint=('data/v1/get' if key else 'public/v1/preview')+('Tariffline' if t['dataset']=='tariffline' else '')
 url=f'{BASE}/{endpoint}/C/{period_frequency(period)}/HS';limit=100000 if key else 500
 params={'reporterCode':t['reporter'],'period':period.replace('-',''),'cmdCode':code,'flowCode':flow,'maxRecords':limit}
 if partners:params['partnerCode']=','.join(partners)
 if t['dataset']=='final':params.update(partner2Code='0',customsCode='C00',motCode='0',breakdownMode='classic')
 snap,source,token=_payload(session,url,params,key,refresh);payload=snap['payload'];data=payload['data'];count=num(payload.get('count'))
 if len(data)>=limit or (count is not None and count>len(data)):return [],'possibly_truncated',token
 return data,source if data else 'empty_not_zero',token

def discover(q,session=None,key=None,progress=lambda x:None,max_attempts=None):
 ts,_=plan(q);session=session or requests.Session();key=os.getenv('COMTRADE_API_KEY','') if key is None else key;out=[]
 for r,ds in dict.fromkeys((t['reporter'],t['dataset']) for t in ts):
  for freq in ('A','M'):
   if max_attempts is not None and len(out)>=max_attempts:return out
   endpoint=('data/v1/getDa' if key else 'public/v1/getDA')+('Tariffline' if ds=='tariffline' else '')
   url=f'{BASE}/{endpoint}/C/{freq}/HS';params={'reporterCode':r};entry=dict(reporter=r,dataset=ds,frequency=freq,status='unknown',periods=[],cache_id='',error='',metadata=[])
   progress(f'Availability · {r} · {ds} · {freq}')
   try:
    snap,source,token=_payload(session,url,params,key,q.get('refresh',False));payload=snap['payload'];entry['cache_id']=token;rows=[row for row in payload['data'] if ident(row.get('reporterCode',r))==r and row.get('freqCode',freq)==freq];periods=set()
    for row in rows:
     v=str(row.get('period',''));v=v.replace('-','')
     if freq=='A' and re.fullmatch(r'\d{4}',v):periods.add(v)
     if freq=='M' and re.fullmatch(r'\d{6}',v):periods.add(v[:4]+'-'+v[4:])
    entry.update(status='listed' if periods else 'empty_or_unrecognized',periods=sorted(periods),metadata=rows[:5],count=len(rows),latest_release=max((str(row.get('lastReleased') or '') for row in rows),default=''),code_lengths=sorted({str(row['lengthCmdCode']) for row in rows if row.get('lengthCmdCode') is not None}))
   except Exception as e:entry.update(status='error',error=safe_error(e,key))
   out.append(entry)
 return out

def safe_error(e,key):
 s=f'{type(e).__name__}: {e}';return s.replace(key,'[REDACTED]')[:500] if key else s[:500]

def normalize(data,t,period,flow,partners):
 groups={};rejected=0;conflicts=0;freq=period_frequency(period);tariff=t['dataset']=='tariffline'
 for row in data:
  p=ident(row.get('partnerCode'));code=str(row.get('cmdCode',''))
  if ident(row.get('reporterCode'))!=t['reporter'] or str(row.get('period','')).replace('-','')!=period.replace('-','') or row.get('freqCode',freq)!=freq or row.get('flowCode')!=flow or code not in t['aliases'] or (partners and p not in partners):rejected+=1;continue
  if p==t['reporter'] or (tariff and p=='0') or not p.isdigit():rejected+=1;continue
  # Unknown partner codes are not silently dropped from tariff lines. They remain unmapped and flagged.
  if not tariff and p not in COUNTRIES:rejected+=1;continue
  groups.setdefault(p,[]).append(row)
 out=[]
 for p,rs in groups.items():
  # Mixed HS editions / aliases can overlap; refuse rather than sum incompatible series.
  if len({(str(x.get('classificationCode')),str(x.get('cmdCode'))) for x in rs})>1:conflicts+=len(rs);continue
  if not tariff:
   rs=list({json.dumps(x,sort_keys=True):x for x in rs}.values())
   total=[x for x in rs if all(str(x.get(k))==v for k,v in [('partner2Code','0'),('customsCode','C00'),('motCode','0')])]
   if len(total)!=1:conflicts+=len(rs);continue
   rejected+=len(rs)-1;rs=total;scope='total_dimensions'
  else:
   # Tariff lines may have indistinguishable rows from finer-grained submissions. Preserve multiplicity.
   # When explicit total and detailed strata coexist, do not risk double counting: exclude ambiguous partner.
   ambiguous=False
   for k,total,unknown in [('partner2Code','0','-1'),('customsCode','C00','-1'),('motCode','0','-1'),('mosCode','0','-1')]:
    vals={str(x.get(k,unknown)) for x in rs}
    if len(vals)>1 and (total in vals or unknown in vals or 'None' in vals):ambiguous=True
   if ambiguous:conflicts+=len(rs);continue
   scope='tariffline_observed_possible_partial'
  def sum_or_none(v):
   vals=[x for x in v if x is not None];return sum(vals) if vals else None
  weights=[];values=[];priced_k=[];priced_v=[]
  for x in rs:
   kg=num(x.get('netWgt'));usd=num(x.get('primaryValue'));kg=None if kg==0 and usd and usd>0 else kg
   weights.append(kg);values.append(usd)
   if kg is not None and kg>0 and usd is not None:priced_k.append(kg);priced_v.append(usd)
  x=rs[0];meta=COUNTRIES.get(p,{'name':f'Unmapped partner ({p})','iso':None});flags=[x.get('isNetWgtEstimated') for x in rs]
  out.append(dict(period=period,frequency=freq,reporter=t['reporter'],hs=t['code'],flow=flow,partner=p,partner_name=meta['name'],iso=meta['iso'],kg=sum_or_none(weights),usd=sum_or_none(values),priced_kg=sum_or_none(priced_k),priced_usd=sum_or_none(priced_v),scope=scope,source_hs=str(x['cmdCode']),tier=t['tier'],estimated=True if True in flags else False if all(v is False for v in flags) else None,classification=x.get('classificationCode'),source_rows=len(rs),missing_weight_rows=sum(v is None for v in weights),missing_value_rows=sum(v is None for v in values)))
 return out,rejected,conflicts

def demo_rows(t,period,flow,partners):
 p=pd.Period(period); i=(p.year-2023)*12+(p.month if period_frequency(period)=='M' else 6); out=[]
 for j,k in enumerate(['410','392','360','276','504','842','704','156']):
  if k==t['reporter'] or (partners and k not in partners):continue
  n=int(hashlib.sha256(f'{t["code"]}{period}{flow}{k}'.encode()).hexdigest()[:8],16)
  kg=round((8-j)*110000*(1+i*.018+(n%100-50)/250)*(1 if flow=='X' else .36)); price=round(15-i*.08+j*.18+(n%20)/20,2)
  out.append(dict(period=period,reporterCode=t['reporter'],partnerCode=k,cmdCode=t['code'],flowCode=flow,netWgt=kg,primaryValue=kg*price,partner2Code=0,customsCode='C00',motCode=0,isNetWgtEstimated=False,classificationCode='DEMO'))
 if t['dataset']=='final' and (not partners or '0' in partners):out.append(dict(period=period,reporterCode=t['reporter'],partnerCode='0',cmdCode=t['code'],flowCode=flow,netWgt=sum(x['netWgt'] for x in out),primaryValue=sum(x['primaryValue'] for x in out),partner2Code=0,customsCode='C00',motCode=0,classificationCode='DEMO'))
 return out

def collect(q,progress=lambda x:None):
 ts,jobs=plan(q); rows=[]; audit=[]; calls=0; failures=0; key=os.getenv('COMTRADE_API_KEY',''); demo=q.get('demo',False); partners=q.get('partners',[]); session=requests.Session()
 availability=[]
 if q.get('frequency')=='auto' and not demo:
  availability=discover(q,session,key,lambda msg:progress(dict(done=0,total=len(jobs),message=msg)),max_attempts=int(q['budget']));calls=len(availability)
  # If a dataset explicitly lists periods, prioritize its listed periods; absence is not proof of zero.
  listed={(a['reporter'],a['dataset'],a['frequency']):set(a['periods']) for a in availability if a['status']=='listed'}
  jobs.sort(key=lambda j: (0 if j[0] in listed.get((j[1]['reporter'],j[1]['dataset'],period_frequency(j[0])),set()) else 1))
 for i,(p,t,f) in enumerate(jobs):
  progress(dict(done=i,total=len(jobs),message=f'{p} · {t["reporter"]} · {t["code"]} · {f}'))
  status='deferred_budget'; data=[]; err=''; cache=[]; used=''; rej=conf=0
  if demo: data=demo_rows(t,p,f,partners);status='synthetic';used=t['code']
  elif failures>=3: status='stopped_after_errors'
  else:
   for code in t['aliases']:
    if calls>=int(q['budget']): status='deferred_budget';break
    calls+=1;used=code
    try:
     data,status,token=request_data(session,t,p,f,code,partners,key,q.get('refresh',False));cache.append(token);failures=0
    except Exception as e:
     status='error';err=safe_error(e,key);failures+=1;break
    if status!='empty_not_zero':break
  clean,rej,conf=normalize(data,t,p,f,partners); rows.extend(clean)
  raw_count=len(data);response_info=[]
  for token in cache:
   path=CACHE/(token+'.json')
   if path.exists():
    snap=json.loads(path.read_text(encoding='utf-8'));payload=snap['payload'];response_info.append(dict(code=snap['params'].get('cmdCode'),http=snap['http'],api_count=payload.get('count'),returned_rows=len(payload['data']),elapsed=payload.get('elapsedTime'),retrieved=snap['retrieved']))
    raw_count=len(payload['data'])
  if data and not clean and status in ('downloaded','cached'):status='excluded_all'
  audit.append(dict(period=p,frequency=period_frequency(p),reporter=t['reporter'],hs=t['code'],flow=f,status=status,raw_rows=raw_count,response_info=response_info,clean_rows=len(clean),source_rows_used=sum(x['source_rows'] for x in clean),excluded=rej,conflicts=conf,queried_code=used,cache_ids=cache,error=err))
 return dict(schema_version=34,availability=availability,mode='SYNTHETIC DEMO' if demo else 'UN Comtrade',query=q,targets=ts,rows=rows,audit=audit,created=datetime.now(timezone.utc).isoformat(),attempts=calls)
