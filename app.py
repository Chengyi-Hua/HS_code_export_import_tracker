from pathlib import Path
import json,uuid,threading,os,io,html,re,argparse
from datetime import datetime,timezone
from fastapi import FastAPI,HTTPException
from fastapi.responses import HTMLResponse,FileResponse,Response
from pydantic import BaseModel,Field
import plotly,plotly.io as pio,pandas as pd,requests
from engine import ROOT,REG,COUNTRIES,plan,collect,discover,period_frequency,CACHE
from analytics import analyze
from presentation import sections,report_html
app=FastAPI(title='pCAM Market Intelligence')
RUNS=ROOT/'data'/'runs';RUNS.mkdir(parents=True,exist_ok=True)
JOBS={};LOCK=threading.Lock()
class Query(BaseModel):
 frequency:str='A'; codes:str='28539030 28539050'; reporters:list[str]=['156']; start:str='2024';end:str='2024';flows:list[str]=['M','X'];partners:list[str]=[];budget:int=100;demo:bool=False;refresh:bool=False

def load(rid):
 if not re.fullmatch(r'[a-f0-9]{32}',rid):raise HTTPException(404,'Invalid run')
 path=RUNS/(rid+'.json')
 if not path.exists():raise HTTPException(404,'Run not found')
 return json.loads(path.read_text(encoding='utf-8'))
@app.get('/')
def index():return FileResponse(ROOT/'web'/'index.html')
@app.get('/plotly.js')
def js():return FileResponse(Path(plotly.__file__).parent/'package_data'/'plotly.min.js',media_type='application/javascript')
@app.get('/api/options')
def options():return dict(registry=REG,countries=COUNTRIES,latest=str(pd.Period(datetime.now(timezone.utc).strftime('%Y-%m'))-1),latest_year=str(datetime.now(timezone.utc).year-1),authenticated=bool(os.getenv('COMTRADE_API_KEY')))
@app.get('/api/hs-search')
def hs_search(q:str):
 q=q.strip().lower()
 if len(q)<2:return []
 path=ROOT/'data'/'hs_reference.json'
 try:
  if not path.exists():
   response=requests.get('https://comtradeapi.un.org/files/v1/app/reference/HS.json',timeout=(5,20));response.raise_for_status();payload=response.json();rows=payload.get('results',[]) if isinstance(payload,dict) else payload
   if not isinstance(rows,list) or not rows:raise ValueError('Unexpected reference format')
   path.write_text(json.dumps(rows),encoding='utf8')
  rows=json.loads(path.read_text(encoding='utf8'));out=[];seen=set()
  for x in rows:
   code=str(x.get('id',x.get('cmdCode','')));desc=str(x.get('text',x.get('cmdDesc','')))
   if re.fullmatch(r'\d{6}',code) and code not in seen and all(w in (code+' '+desc).lower() for w in q.split()):
    out.append(dict(code=code,label=desc));seen.add(code)
  return out[:60]
 except Exception as e:raise HTTPException(502,'Reference lookup unavailable; use curated registry or manual code. '+str(e)[:180])
@app.post('/api/plan')
def preview(query:Query):
 q=query.model_dump() if hasattr(query,'model_dump') else query.dict()
 try:t,j=plan(q);return dict(targets=t,jobs=len(j),max_attempts=sum(len(x[1]['aliases']) for x in j)+(2*len({(x['reporter'],x['dataset']) for x in t}) if q['frequency']=='auto' and not q['demo'] else 0),annual_jobs=sum(period_frequency(x[0])=='A' for x in j),monthly_jobs=sum(period_frequency(x[0])=='M' for x in j),budget=q['budget'])
 except Exception as e:raise HTTPException(400,str(e))
@app.post('/api/discover')
def availability(query:Query):
 q=query.model_dump() if hasattr(query,'model_dump') else query.dict()
 try:
  if q['demo']:raise ValueError('Disable demo mode to check live availability.')
  return discover(q,max_attempts=q['budget'])
 except ValueError as e:raise HTTPException(400,str(e))
@app.post('/api/run')
def run(query:Query):
 q=query.model_dump() if hasattr(query,'model_dump') else query.dict();preview(query)
 with LOCK:
  if any(x['status']=='running' for x in JOBS.values()):raise HTTPException(409,'Another retrieval is running')
  rid=uuid.uuid4().hex;JOBS[rid]=dict(status='running',done=0,total=0,message='Starting')
 def worker():
  try:
   result=collect(q,lambda p:JOBS[rid].update(p));result['id']=rid;tmp=RUNS/(rid+'.tmp');tmp.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');tmp.replace(RUNS/(rid+'.json'));JOBS[rid].update(status='finished',message='Complete')
  except Exception as e:JOBS[rid].update(status='error',message=str(e))
 threading.Thread(target=worker,daemon=True).start();return {'id':rid}
@app.get('/api/status/{rid}')
def status(rid:str):return JOBS.get(rid,{'status':'finished'} if (RUNS/(rid+'.json')).exists() else {'status':'unknown'})
@app.get('/api/runs')
def runs():
 out=[]
 for p in sorted(RUNS.glob('*.json'),key=lambda x:x.stat().st_mtime,reverse=True):
  r=json.loads(p.read_text(encoding='utf-8'));out.append({k:r[k] for k in ['id','mode','query','created']}|{'rows':len(r['rows'])})
 return out
@app.get('/api/run/{rid}')
def getrun(rid:str):
 r=load(rid);series={}
 for a in r['audit']:
  freq=a.get('frequency',period_frequency(a['period']));k=(a['reporter'],a['hs'],a['flow'],freq);g=series.setdefault(k,dict(reporter=k[0],hs=k[1],flow=k[2],frequency=freq,start=a['period'],end=a['period'],rows=0,usable_periods=0,latest_usable='',partners=[]))
  g['start']=min(g['start'],a['period']);g['end']=max(g['end'],a['period']);g['rows']+=a['clean_rows'];g['usable_periods']+=bool(a['clean_rows']);g['latest_usable']=max(g['latest_usable'],a['period'] if a['clean_rows'] else '')
 for x in r['rows']:
  g=series.get((x['reporter'],x['hs'],x['flow'],x.get('frequency',period_frequency(x['period']))))
  if g and x['partner']!='0' and [x['partner'],x['partner_name']] not in g['partners']:g['partners'].append([x['partner'],x['partner_name']])
 return {k:r[k] for k in ['id','mode','query','targets','created','attempts']}|{'rows':len(r['rows']),'series':list(series.values()),'schema_version':r.get('schema_version',0)}
def view(rid,reporter,hs,flow,scope,partners,start,end,frequency=''):
 r=load(rid)
 if scope not in ['partners','world'] or flow not in r['query']['flows'] or frequency not in ('','A','M'):raise HTTPException(400,'Invalid scope/flow/frequency')
 try:
  v=analyze(r,reporter,hs,flow,scope,partners.split(',') if partners else None,start,end,frequency or None);v['sections']=sections(v['charts']);return v
 except Exception as e:raise HTTPException(400,str(e))
@app.get('/api/raw/{rid}/{token}')
def raw(rid:str,token:str):
 r=load(rid)
 allowed={c for a in r['audit'] for c in a.get('cache_ids',[])}|{a.get('cache_id') for a in r.get('availability',[])}
 if not re.fullmatch(r'[a-f0-9]{64}',token) or token not in allowed:raise HTTPException(404,'Unknown raw snapshot')
 path=CACHE/(token+'.json')
 if not path.exists():raise HTTPException(404,'Raw snapshot unavailable (legacy run or deleted cache)')
 return FileResponse(path,media_type='application/json',filename=token+'.json')
@app.get('/api/view/{rid}')
def dashboard(rid:str,reporter:str,hs:str,flow:str='X',scope:str='partners',partners:str='',start:str='',end:str='',frequency:str=''):return view(rid,reporter,hs,flow,scope,partners,start,end,frequency)
@app.get('/api/export/{rid}/{kind}')
def export(rid:str,kind:str,reporter:str='',hs:str='',flow:str='X',scope:str='partners',partners:str='',start:str='',end:str='',frequency:str=''):
 r=load(rid)
 if kind in ['rows','audit']:
  csv=pd.DataFrame(r['rows' if kind=='rows' else 'audit']).to_csv(index=False);return Response(csv,media_type='text/csv',headers={'Content-Disposition':f'attachment; filename={kind}.csv'})
 if kind=='json':return Response(json.dumps(r,indent=2),media_type='application/json',headers={'Content-Disposition':'attachment; filename=run.json'})
 v=view(rid,reporter,hs,flow,scope,partners,start,end,frequency)
 if kind=='xlsx':
  b=io.BytesIO()
  with pd.ExcelWriter(b,engine='xlsxwriter',engine_kwargs={'options':{'strings_to_formulas':False,'strings_to_urls':False}}) as w:
   for name,data in [('Overview',[{'metric':x[0],'value':x[1],'context':x[2]} for x in v['kpis']]),('Notes',[{'note':x} for x in v['notes']]),*v['tables'].items(),('Audit',v['audit'])]:
    df=pd.DataFrame(data);df.to_excel(w,sheet_name=name[:31],index=False);s=w.sheets[name[:31]];s.freeze_panes(1,0);s.set_column(0,max(0,len(df.columns)-1),24)
  return Response(b.getvalue(),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename=trade_analysis.xlsx'})
 if kind!='html':raise HTTPException(404,'Unknown export')
 doc=report_html(v,r,scope);return HTMLResponse(doc,headers={'Content-Disposition':'attachment; filename=market_intelligence.html'})
if __name__=='__main__':
 import uvicorn
 uvicorn.run(app,host='127.0.0.1',port=8765)
