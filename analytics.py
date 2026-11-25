import pandas as pd,numpy as np,plotly.graph_objects as go,plotly.io as pio,json,html,io
from engine import COUNTRIES,period_frequency
PALETTE=['#1565A5','#D18C21','#596674','#39434D','#45A1B4','#8874A6','#A2ABB5']
SEQUENTIAL=[[0,'#F1F5F9'],[.25,'#D1E1F0'],[.5,'#94B9DC'],[.75,'#4C87BA'],[1,'#174E80']]
def figure(title,y=None):
 f=go.Figure();f.update_layout(title=dict(text=title,x=.02,font=dict(size=15,color='#20242A',family='Arial, Helvetica, sans-serif')),template='none',font=dict(family='Arial, Helvetica Neue, sans-serif',color='#424C56',size=12),colorway=PALETTE,margin=dict(l=62,r=25,t=57,b=66),height=345,legend=dict(orientation='h',y=-.20,font=dict(size=10)),yaxis_title=y,hovermode='closest',paper_bgcolor='#ffffff',plot_bgcolor='#ffffff',xaxis=dict(gridcolor='#E9EDF0',automargin=True),yaxis=dict(gridcolor='#E1E6EB',zerolinecolor='#AEB8C2',automargin=True));return f
def serial(f):return json.loads(pio.to_json(f))
def fmt(x,s=''):return 'Unavailable' if pd.isna(x) else f'{x:,.1f}{s}'
def pct(a,b):return (a/b-1)*100 if pd.notna(a) and pd.notna(b) and b>0 else np.nan
def aggregate(d,keys):
 x=d.groupby(keys,dropna=False)[['kg','usd','priced_kg','priced_usd']].sum(min_count=1).reset_index();x['t']=x.kg/1000;x['price']=x.priced_usd/x.priced_kg.where(x.priced_kg>0);return x

def analyze(run,reporter,hs,flow,scope='partners',selected=None,start=None,end=None,frequency=None):
 t=next((t for t in run['targets'] if t['reporter']==reporter and t['code']==hs),None)
 if not t:raise ValueError('Unknown target')
 frequency=frequency or (run['query'].get('frequency','M') if run['query'].get('frequency') in ('A','M') else 'M')
 annual=frequency=='A'; step=1 if annual else 12; unit='year' if annual else 'month'; title_unit='Annual' if annual else 'Monthly'; freq='Y' if annual else 'M'
 audit=[a for a in run['audit'] if a['reporter']==reporter and a['hs']==hs and a['flow']==flow and a.get('frequency',period_frequency(a['period']))==frequency]
 if not audit:raise ValueError('No requested periods for this reporting frequency.')
 start=start or min(a['period'] for a in audit);end=end or max(a['period'] for a in audit)
 if start<min(a['period'] for a in audit) or end>max(a['period'] for a in audit) or start>end or period_frequency(start)!=frequency or period_frequency(end)!=frequency:raise ValueError('Period outside retrieval or wrong frequency.')
 periods=[str(p) for p in pd.period_range(start,end,freq=freq)];audit=[a for a in audit if a['period'] in periods]
 d=pd.DataFrame([r for r in run['rows'] if r['reporter']==reporter and r['hs']==hs and r['flow']==flow and r.get('frequency',period_frequency(r['period']))==frequency and r['period'] in periods]);charts=[];notes=[];kpis=[];tables={}
 availability=[a for a in run.get('availability',[]) if a['reporter']==reporter and a['dataset']==t['dataset']]
 if availability:tables['dataset_availability']=[{**{k:v for k,v in a.items() if k not in ('metadata','periods')},'period_count':len(a['periods']),'first_period':min(a['periods'],default=''),'last_period':max(a['periods'],default=''),'listed_periods':', '.join(a['periods'])} for a in availability]
 subtitle=f'{COUNTRIES[reporter]["name"]} | HS {hs} | {"Exports" if flow=="X" else "Imports"} | {t["tier"]} | {title_unit} | {start} to {end}'
 def add(f):
  # Annual/month labels are discrete periods, not daily dates.
  if any(getattr(tr,'x',None) is not None and any(str(v) in periods for v in tr.x) for tr in f.data):f.update_xaxes(type='category',categoryorder='array',categoryarray=periods)
  charts.append(serial(f))
 f=figure('01 / Retrieval coverage'); statuses=['downloaded','cached','synthetic','empty_not_zero','possibly_truncated','deferred_budget','error','stopped_after_errors','excluded_all']; colors=['#287A57','#287A57','#8793A0','#D69B30','#B34745','#B8C0C8','#B34745','#B34745','#B34745']; sm={a['period']:a for a in audit}; f.add_trace(go.Bar(x=periods,y=[1]*len(periods),marker_color=[colors[statuses.index(sm[p]['status'])] if p in sm and sm[p]['status'] in statuses else '#E3E7EB' for p in periods],text=[sm.get(p,{}).get('status','not queried') for p in periods],hovertemplate='%{x}<br>%{text}<extra></extra>'));f.update_yaxes(visible=False);add(f)
 if d.empty:return dict(title=subtitle,mode=run['mode'],kpis=[],notes=['No usable observations. Empty or failed retrieval is not zero trade. Review the audit and try another reporting frequency.'],charts=charts,audit=audit,tables=tables,tier=t['tier'])
 for c in ['kg','usd','priced_kg','priced_usd']:d[c]=pd.to_numeric(d[c],errors='coerce')
 routes=d[d.partner!='0'].copy(); routes=routes[routes.partner.isin(selected)] if selected else routes
 base=d[d.partner=='0'] if scope=='world' else routes
 if base.empty:return dict(title=subtitle,mode=run['mode'],kpis=[],notes=['No records for this scope. Switch to observed partners if world totals are unavailable.'],charts=charts,audit=audit,tables=tables,tier=t['tier'])
 monthly=aggregate(base,['period']).set_index('period').reindex(periods);latest=monthly.dropna(subset=['kg','usd'],how='all').index[-1] if monthly[['kg','usd']].notna().any().any() else periods[-1];last=monthly.loc[latest];prev=str(pd.Period(latest,freq=freq)-step);mom=str(pd.Period(latest,freq=freq)-1); old=monthly.loc[prev] if prev in monthly.index else pd.Series(dtype=float)
 yoy=pct(last.t,old.get('t',np.nan));m=pct(last.t,monthly.loc[mom,'t'] if mom in monthly.index else np.nan);uv=pct(last.price,old.get('price',np.nan));
 kpis=[['Latest volume',('Unavailable' if pd.isna(last.t) else f'{last.t:,.3f} t' if abs(last.t)<1 else fmt(last.t,' t')),f'{fmt(yoy,"% ")} YoY'+('' if annual else f' · {fmt(m,"% ")} MoM')],['Trade value',('Unavailable' if pd.isna(last.usd) else f'{last.usd:,.0f} USD' if abs(last.usd)<1e6 else fmt(last.usd/1e6,' M USD')),latest],['Weighted unit value',fmt(last.price,' USD/kg'),f'{fmt(uv,"% ")} YoY'],[f'Latest observed {unit}',latest,f'{len(monthly.dropna(subset=["kg","usd"],how="all"))}/{len(periods)} {unit}s with data']]
 notes=[('Reported world totals' if scope=='world' else 'Observed partner sums only; not total national or global trade.')+' Changes can reflect reporting coverage.',f'Latest usable {unit}: {latest}. Missing {unit}s are not zeros. Unit value is customs value per matched net kg, not a contract price.']
 if pd.notna(yoy) and pd.notna(uv):notes.append(f'Volume changed {yoy:+.1f}% YoY while unit value changed {uv:+.1f}% YoY. Product mix and valuation may explain part of this change.')
 if t['tier']!='specific':notes.append('Proxy or custom classification: do not interpret as pCAM-specific trade.')
 if (base.scope!='total_dimensions').any():notes.append('National tariff-line totals sum returned observations, not certified national totals; repeated records are preserved, ambiguous overlapping dimensions excluded.')
 if annual:notes.append('Annual observations cover whole calendar years. Annual and monthly series are never combined. MoM and seasonality are not applicable.')
 if run.get('schema_version',0)<34 and run['mode']!='SYNTHETIC DEMO':notes.append('Legacy run from v3.3 or older: re-retrieve before relying on results; previous cleaning may have dropped tariff-line records.')
 if base.get('missing_weight_rows',pd.Series(dtype=float)).gt(0).any():notes.append('Some contributing source records lack usable weights; observed volume is partial and unit value uses only matched weight/value.')
 if base.get('missing_value_rows',pd.Series(dtype=float)).gt(0).any():notes.append('Some contributing source records lack trade value; displayed value is partial.')
 if base.partner_name.str.startswith('Unmapped partner').any():notes.append('Some tariff-line partner codes are unmapped; retained in observed totals but not geographically located.')
 if selected:notes.append('Partner selection restricts observed totals to selected routes.')
 if base.classification.nunique()>1:notes.append('Multiple HS classification editions are present; verify code continuity before comparing periods.')
 if base.estimated.eq(True).any():notes.append('Some net weights were estimated by the source.')
 if base.kg.isna().any():notes.append('Some records lack valid net weight. Volumes and unit values cover available weights only.')
 if any(a['status'] not in ['downloaded','cached','synthetic'] or a['conflicts'] or a['excluded'] for a in audit):notes.append('Coverage exclusions, failed requests or missing data exist. Review audit before drawing conclusions.')
 for c,label in [('t',f'{title_unit} volume (tonnes)'),('usd',f'{title_unit} trade value (USD)'),('price','Weighted customs unit value (USD/kg)')]:
  f=figure(label,label);f.add_trace(go.Scatter(x=periods,y=monthly[c],mode='lines+markers',name=label,connectgaps=False));
  if c=='t' and not annual:f.add_trace(go.Scatter(x=periods,y=monthly.t.rolling(12,min_periods=12).sum()/12,name='12-month average',line=dict(dash='dash')))
  add(f)
 f=figure('Volume, value and unit value | indexed to common baseline','Index (base = 100)'); common=monthly[(monthly[['t','usd','price']]>0).all(axis=1)];
 if not common.empty:
  first=common.index[0]
  for c,l in [('t','Volume'),('usd','Value'),('price','Unit value')]:f.add_trace(go.Scatter(x=periods,y=monthly[c]/monthly.loc[first,c]*100,name=l,mode='lines+markers',connectgaps=False))
  f.add_hline(y=100,line_dash='dot')
 add(f)
 if not annual:
  f=figure('Rolling 12-month volume','Tonnes');f.add_trace(go.Scatter(x=periods,y=monthly.t.rolling(12,min_periods=12).sum(),fill='tozeroy',name='Rolling total'));add(f)
  f=figure('Seasonality | month by year','Year');s=monthly.copy();s['year']=[p[:4] for p in periods];s['month']=[p[5:] for p in periods];z=s.pivot(index='year',columns='month',values='t').reindex(columns=[f'{i:02}' for i in range(1,13)]);f.add_trace(go.Heatmap(z=z.values,x=z.columns,y=z.index,colorscale=SEQUENTIAL,colorbar=dict(title='t')));add(f)
 f=figure('Year-on-year growth' if annual else 'Month-on-month and year-on-year growth','%');
 for n,l in ([(1,'YoY')] if annual else [(1,'MoM'),(12,'YoY')]):f.add_trace(go.Bar(x=periods,y=(monthly.t/monthly.t.shift(n).where(monthly.t.shift(n)>0)-1)*100,name=l))
 add(f)
 # Price/value decomposition uses matched weight/value only, exact symmetric decomposition.
 if prev in monthly.index and all(pd.notna(v) for v in [last.price,old.get('price'),last.priced_kg,old.get('priced_kg')]):
  q0,q1=old.priced_kg,last.priced_kg;p0,p1=old.price,last.price;vol=(q1-q0)*(p1+p0)/2;pr=(p1-p0)*(q1+q0)/2
  f=figure('YoY matched trade value bridge','USD');f.add_trace(go.Waterfall(x=['Prior year','Volume effect','Unit value effect','Current'],measure=['absolute','relative','relative','total'],y=[q0*p0,vol,pr,0],increasing=dict(marker=dict(color='#287A57')),decreasing=dict(marker=dict(color='#B34745')),totals=dict(marker=dict(color='#39434D')),connector=dict(line=dict(color='#A2ABB5'))));add(f)
 if len(periods)>=7 and monthly.t.notna().sum()>=7:
  f=figure('Unusual volume movements | historical rolling z-score','z-score');avg=monthly.t.shift().rolling(6,min_periods=6).mean();std=monthly.t.shift().rolling(6,min_periods=6).std();f.add_trace(go.Scatter(x=periods,y=(monthly.t-avg)/std.where(std>0),mode='lines+markers'));f.add_hline(y=3,line_dash='dot');f.add_hline(y=-3,line_dash='dot');add(f)
 # A transparent seasonal-naive scenario, never presented as a validated demand forecast.
 if not annual and len(monthly)>=24 and monthly.t.iloc[-24:].notna().all():
  hist=monthly.t.iloc[-12:];back=monthly.t.iloc[-24:-12].to_numpy();err=np.mean(np.abs(hist.to_numpy()-back));future=[str(pd.Period(periods[-1])+i) for i in range(1,7)]
  f=figure('Seasonal-naive trade scenario | not demand forecast','Tonnes');f.add_trace(go.Scatter(x=periods,y=monthly.t,name='Observed'));f.add_trace(go.Scatter(x=future,y=hist.iloc[:6],name='Prior-year seasonal scenario',line=dict(dash='dash')));add(f);notes.append(f'Seasonal-naive scenario repeats the prior-year monthly pattern; last-12-month backtest MAE {err:,.0f} t. No causal drivers, forecasts of demand or confidence intervals are inferred.')
 # Mirror check only for exactly the same six-digit code; no national-code equivalence assumed.
 if len(hs)==6 and not routes.empty:
  opposite='M' if flow=='X' else 'X'; mirrors=pd.DataFrame([x for x in run['rows'] if x['hs']==hs and x['flow']==opposite and x['partner']==reporter and x['period'] in periods and x['scope']=='total_dimensions'])
  if not mirrors.empty:
   for c in ['kg','usd','priced_kg','priced_usd']:mirrors[c]=pd.to_numeric(mirrors[c],errors='coerce')
   left=routes[routes.scope=='total_dimensions'].groupby(['period','partner']).kg.sum(min_count=1).reset_index();right=mirrors.groupby(['period','reporter']).kg.sum(min_count=1).reset_index().rename(columns={'reporter':'partner','kg':'mirror_kg'});m=left.merge(right,on=['period','partner']);m=m.dropna(subset=['kg','mirror_kg']);
   if not m.empty:
    f=figure('Mirror trade check | same six-digit HS','Counterpart tonnes');f.add_trace(go.Scatter(x=m.kg/1000,y=m.mirror_kg/1000,mode='markers',text=m.period+' · '+m.partner,hovertemplate='%{text}<br>Reporter %{x:,.0f} t<br>Counterpart %{y:,.0f} t<extra></extra>'));mx=max(m.kg.max(),m.mirror_kg.max())/1000;f.add_trace(go.Scatter(x=[0,mx],y=[0,mx],mode='lines',name='Equality',line=dict(dash='dot')));f.update_xaxes(title='Reporter tonnes');add(f);tables['mirror']=json.loads(m.to_json(orient='records'));notes.append('Mirror differences can reflect origin/destination definitions, timing, re-exports and statistical methods; same six-digit code does not guarantee equivalent products.')
 if not routes.empty:
  r=aggregate(routes,['period','partner','partner_name','iso']); now=r[r.period==latest].sort_values('t',ascending=False); top=now.dropna(subset=['t']).head(12); total=now.t.sum(min_count=1)
  if not top.empty and total>0:
   leader=top.iloc[0];kpis.append(['Leading observed partner',leader.partner_name,f'{leader.t/total:.1%} of observed volume']);notes.append(f'{leader.partner_name} accounts for {leader.t/total:.1%} of observed partner volume in {latest}. This is not global market share.')
   f=figure('Leading observed trading partners | latest '+unit,'Tonnes');f.add_trace(go.Bar(y=top.partner_name[::-1],x=top.t[::-1],orientation='h',marker_color=PALETTE[0],text=[f'{x:,.0f}' for x in top.t[::-1]],textposition='auto'));f.update_layout(yaxis_title=None);add(f)
   f=figure('Trade routes | observed volume');names=[COUNTRIES[reporter]['name']]+top.partner_name.tolist();f.add_trace(go.Sankey(node=dict(label=names,pad=15,thickness=16,color=PALETTE[0]),link=dict(source=[0]*len(top) if flow=='X' else list(range(1,len(top)+1)),target=list(range(1,len(top)+1)) if flow=='X' else [0]*len(top),value=top.t.tolist(),color='rgba(21,101,165,0.24)')));add(f)
   f=figure('Geographic footprint | observed tonnes');f.add_trace(go.Choropleth(locations=top.iso,z=top.t,text=top.partner_name,colorscale=SEQUENTIAL,colorbar=dict(title='t')));f.update_geos(showframe=False,showcoastlines=True,projection_type='natural earth',landcolor='#E9EDF0',coastlinecolor='#A9B4BF',bgcolor='#ffffff',showland=True);add(f)
   pivot=r.pivot(index='period',columns='partner_name',values='t').reindex(periods); names=top.partner_name.tolist(); shares=pivot.div(pivot.sum(axis=1,min_count=1),axis=0);f=figure('Destination / origin share evolution','Observed share');
   for n in names[:6]:f.add_trace(go.Scatter(x=periods,y=shares[n]*100,name=n,mode='lines+markers',connectgaps=False))
   add(f);f=figure('Market concentration | HHI and top-three share','Index / %');f.add_trace(go.Scatter(x=periods,y=(shares**2).sum(axis=1,min_count=1)*100,name='HHI × 100',mode='lines+markers'));f.add_trace(go.Scatter(x=periods,y=shares.apply(lambda x:x.nlargest(3).sum(min_count=1),axis=1)*100,name='Top 3 share (%)',mode='lines+markers'));add(f)
   f=figure(f'Partner heatmap | {unit}ly volumes');f.add_trace(go.Heatmap(x=periods,y=names,z=pivot[names].T.values,colorscale=SEQUENTIAL,colorbar=dict(title='t')));add(f)
   f=figure('Partner unit values | latest '+unit,'USD/kg');f.add_trace(go.Bar(x=top.partner_name,y=top.price));add(f)
   f=figure('Partner ranking shifts | observed volume rank','Rank');rank=pivot.rank(axis=1,ascending=False,method='min');
   for n in names[:6]:f.add_trace(go.Scatter(x=periods,y=rank[n],mode='lines+markers',name=n,connectgaps=False))
   f.update_yaxes(autorange='reversed',dtick=1);add(f)
   f=figure(f'Unit value dispersion | {unit}ly partner observations','USD/kg');
   for n in names[:6]:f.add_trace(go.Box(y=r.loc[r.partner_name==n,'price'],name=n,boxpoints='outliers'))
   add(f)
   prices=r.pivot(index='period',columns='partner_name',values='price').reindex(periods);f=figure('Unit value trends by leading partner','USD/kg');
   for n in names[:6]:f.add_trace(go.Scatter(x=periods,y=prices[n],name=n,mode='lines+markers',connectgaps=False))
   add(f)
   prior=r[r.period==prev][['partner','t']].rename(columns={'t':'prior_t'});comp=now.merge(prior,on='partner',how='inner');comp['delta']=comp.t-comp.prior_t;comp['growth']=(comp.t/comp.prior_t.where(comp.prior_t>0)-1)*100;comp=comp.dropna(subset=['delta']);
   if not comp.empty:
    f=figure('YoY growth contribution | matched partners','Tonnes');c=comp.sort_values('delta');f.add_trace(go.Bar(y=c.partner_name,x=c.delta,orientation='h',marker_color=['#287A57' if x>=0 else '#B34745' for x in c.delta]));f.update_layout(yaxis_title=None);add(f)
    c=comp.dropna(subset=['growth','price','t']);f=figure('Market screening | growth vs unit value','USD/kg');f.add_trace(go.Scatter(x=c.growth,y=c.price,mode='markers+text',text=c.partner_name,textposition='top center',marker=dict(size=np.maximum(9,np.sqrt(c.t.clip(lower=0))*1.1),sizemode='diameter',color=PALETTE[0],opacity=.7),customdata=c.t,hovertemplate='%{text}<br>Growth %{x:.1f}%<br>USD/kg %{y:.2f}<br>Tonnes %{customdata:,.0f}<extra></extra>'));f.update_xaxes(title='YoY observed volume growth (%)');f.add_vline(x=0,line_dash='dot');add(f)
    notes.append('Opportunity matrix is a screening signal only, not profitability or total market demand. Growth contribution covers matched partners only; unmatched routes are not assumed zero.')
    tables['matched_growth']=json.loads(comp.to_json(orient='records'))
   tables['partners_latest']=json.loads(now.to_json(orient='records'))
 tables['bilateral']=json.loads(aggregate(routes,['period','partner','partner_name']).to_json(orient='records')) if not routes.empty else []
 tables['annual' if annual else 'monthly']=json.loads(monthly.reset_index().to_json(orient='records'))
 return dict(title=subtitle,mode=run['mode'],kpis=kpis,notes=notes,charts=charts,audit=audit,tables=tables,tier=t['tier'])
